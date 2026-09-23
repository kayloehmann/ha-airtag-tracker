"""Config flow for AirTag Tracker."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

import voluptuous as vol
from findmy import (
    AsyncAppleAccount,
    AsyncSmsSecondFactor,
    AsyncTrustedDeviceSecondFactor,
    FindMyAccessory,
    InvalidCredentialsError,
    LocalAnisetteProvider,
    LoginState,
)
from homeassistant import config_entries
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    ANISETTE_LIBS_FILENAME,
    CONF_ACCESSORY,
    CONF_ACCOUNT,
    CONF_EMAIL,
    CONF_INSIDE_POLL_INTERVAL,
    CONF_NAME,
    CONF_OUTSIDE_POLL_INTERVAL,
    DEFAULT_INSIDE_POLL_INTERVAL,
    DEFAULT_OUTSIDE_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .helpers import sanitized_account_state

_LOGGER = logging.getLogger(__name__)

LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
        vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)
CODE_SCHEMA = vol.Schema(
    {vol.Required("code"): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))}
)
ACCESSORY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): str,
        vol.Required("file"): FileSelector(FileSelectorConfig(accept=".json,.plist")),
    }
)


class AirTagTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup and reauthentication."""

    VERSION = 1

    def __init__(self) -> None:
        self._account: AsyncAppleAccount | None = None
        self._email: str | None = None
        self._methods: list[AsyncSmsSecondFactor | AsyncTrustedDeviceSecondFactor] = []
        self._method: AsyncSmsSecondFactor | AsyncTrustedDeviceSecondFactor | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Authenticate an Apple account."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=LOGIN_SCHEMA)

        email = str(user_input[CONF_EMAIL]).strip().lower()
        await self.async_set_unique_id(email)
        self._abort_if_unique_id_configured()
        return await self._async_login(email, str(user_input["password"]), "user")

    async def _async_login(self, email: str, password: str, step_id: str):
        self._email = email
        libs_path = self.hass.config.path(".storage", ANISETTE_LIBS_FILENAME)
        self._account = AsyncAppleAccount(anisette=LocalAnisetteProvider(libs_path=libs_path))
        try:
            state = await self._account.login(email, password)
        except InvalidCredentialsError:
            await self._close_pending_account()
            return self.async_show_form(
                step_id=step_id,
                data_schema=REAUTH_SCHEMA if step_id == "reauth_confirm" else LOGIN_SCHEMA,
                errors={"base": "invalid_auth"},
                description_placeholders={"email": email},
            )
        except Exception:
            _LOGGER.exception("Apple authentication failed for %s", email)
            await self._close_pending_account()
            return self.async_show_form(
                step_id=step_id,
                data_schema=REAUTH_SCHEMA if step_id == "reauth_confirm" else LOGIN_SCHEMA,
                errors={"base": "cannot_connect"},
                description_placeholders={"email": email},
            )

        if state == LoginState.REQUIRE_2FA:
            return await self.async_step_two_factor_method()
        return await self._async_login_complete()

    async def async_step_two_factor_method(self, user_input: dict[str, Any] | None = None):
        """Choose how Apple should deliver the verification code."""
        if self._account is None:
            return self.async_abort(reason="flow_expired")
        if user_input is None:
            try:
                self._methods = list(await self._account.get_2fa_methods())
            except Exception:
                _LOGGER.exception("Unable to retrieve Apple two-factor methods")
                return self.async_abort(reason="cannot_connect")
            options: list[SelectOptionDict] = []
            for index, method in enumerate(self._methods):
                label = (
                    f"SMS {method.phone_number}"
                    if isinstance(method, AsyncSmsSecondFactor)
                    else "Trusted Apple device"
                )
                options.append({"label": label, "value": str(index)})
            if not options:
                return self.async_abort(reason="no_2fa_method")
            schema = vol.Schema(
                {vol.Required("method"): SelectSelector(SelectSelectorConfig(options=options))}
            )
            return self.async_show_form(step_id="two_factor_method", data_schema=schema)

        try:
            self._method = self._methods[int(user_input["method"])]
            await self._method.request()
        except Exception:
            _LOGGER.exception("Unable to request Apple two-factor code")
            return self.async_show_form(
                step_id="two_factor_method",
                data_schema=vol.Schema({vol.Required("method"): str}),
                errors={"base": "cannot_connect"},
            )
        return await self.async_step_two_factor_code()

    async def async_step_two_factor_code(self, user_input: dict[str, Any] | None = None):
        """Validate an Apple verification code."""
        if user_input is None:
            return self.async_show_form(step_id="two_factor_code", data_schema=CODE_SCHEMA)
        if self._method is None:
            return self.async_abort(reason="flow_expired")
        try:
            state = await self._method.submit(str(user_input["code"]).strip())
        except Exception:
            _LOGGER.exception("Apple rejected the two-factor code")
            return self.async_show_form(
                step_id="two_factor_code",
                data_schema=CODE_SCHEMA,
                errors={"base": "invalid_code"},
            )
        if state != LoginState.LOGGED_IN:
            return self.async_show_form(
                step_id="two_factor_code",
                data_schema=CODE_SCHEMA,
                errors={"base": "invalid_code"},
            )
        return await self._async_login_complete()

    async def _async_login_complete(self):
        """Continue to upload or finish reauthentication."""
        if self._account is None:
            return self.async_abort(reason="flow_expired")
        if self._reauth_entry is not None:
            data = dict(self._reauth_entry.data)
            data[CONF_ACCOUNT] = sanitized_account_state(self._account.to_json())
            await self._close_pending_account()
            return self.async_update_reload_and_abort(self._reauth_entry, data=data)
        return await self.async_step_accessory()

    async def async_step_accessory(self, user_input: dict[str, Any] | None = None):
        """Import the AirTag's end-to-end encryption keys."""
        if user_input is None:
            return self.async_show_form(step_id="accessory", data_schema=ACCESSORY_SCHEMA)
        try:
            accessory = await self.hass.async_add_executor_job(
                _load_accessory,
                self.hass,
                str(user_input["file"]),
            )
        except OSError, ValueError, KeyError, AssertionError:
            return self.async_show_form(
                step_id="accessory",
                data_schema=ACCESSORY_SCHEMA,
                errors={"base": "invalid_accessory"},
            )
        if name := str(user_input.get(CONF_NAME, "")).strip():
            accessory.name = name
        if not accessory.identifier:
            return self.async_show_form(
                step_id="accessory",
                data_schema=ACCESSORY_SCHEMA,
                errors={"base": "invalid_accessory"},
            )
        if self._account is None or self._email is None:
            return self.async_abort(reason="flow_expired")
        data = {
            CONF_EMAIL: self._email,
            CONF_ACCOUNT: sanitized_account_state(self._account.to_json()),
            CONF_ACCESSORY: accessory.to_json(),
        }
        title = accessory.name or "AirTag"
        await self._close_pending_account()
        return self.async_create_entry(title=title, data=data)

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Start reauthentication after Apple expires a session."""
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="flow_expired")
        self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reauth_entry is None:
            return self.async_abort(reason="flow_expired")
        self._email = str(entry_data[CONF_EMAIL])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Ask only for the password; the account identity cannot be changed."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
                description_placeholders={"email": self._email or ""},
            )
        return await self._async_login(
            self._email or "", str(user_input["password"]), "reauth_confirm"
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return AirTagOptionsFlow(config_entry)

    @callback
    def async_remove(self) -> None:
        """Close a pending Apple session when a flow is cancelled."""
        if self._account is not None:
            self.hass.async_create_task(
                self._close_pending_account(),
                "close cancelled AirTag Tracker setup session",
            )

    async def _close_pending_account(self) -> None:
        if self._account is not None:
            await self._account.close()
            self._account = None


class AirTagOptionsFlow(config_entries.OptionsFlow):
    """Configure a safe polling interval."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        inside = self._entry.options.get(CONF_INSIDE_POLL_INTERVAL, DEFAULT_INSIDE_POLL_INTERVAL)
        outside = self._entry.options.get(CONF_OUTSIDE_POLL_INTERVAL, DEFAULT_OUTSIDE_POLL_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_INSIDE_POLL_INTERVAL, default=inside): NumberSelector(
                    NumberSelectorConfig(
                        min=15,
                        max=MAX_POLL_INTERVAL,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_OUTSIDE_POLL_INTERVAL, default=outside): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_POLL_INTERVAL,
                        max=14,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _load_accessory(hass, file_id: str) -> FindMyAccessory:
    """Load an uploaded FindMy.py JSON or decrypted plist file."""
    with process_uploaded_file(hass, file_id) as uploaded_path:
        content = uploaded_path.read_bytes()
    for loader in (FindMyAccessory.from_json, FindMyAccessory.from_plist):
        try:
            return loader(BytesIO(content))
        except ValueError, KeyError, AssertionError:
            continue
    raise ValueError("Unsupported AirTag key file")
