# AirTag Tracker for Home Assistant

This custom integration signs in to Apple's private Find My service, downloads the
encrypted location reports for one AirTag, decrypts them locally, and exposes the result
to Home Assistant.

It creates:

- a GPS `device_tracker` that participates in normal Home Assistant zones;
- `Last seen`, `Report age`, `Location accuracy`, and `Battery level` sensors;
- tracker attributes for the active zone, polling mode, next polling interval, report
  timestamp, and confidence.

The polling cadence is adaptive by default:

- **inside any Home Assistant zone:** every 15 minutes;
- **outside all Home Assistant zones:** every 5 minutes.

Both values are configurable under the integration's options. The outside interval can
be 2–14 minutes; the inside interval can be 15–60 minutes. Apple has no public AirTag API,
so aggressive polling can trigger throttling or account lockouts.

## Important limitations

This is an unofficial integration. Apple can change or disable the private protocol at
any time. Do not use an AirTag or this integration as the sole safety mechanism for
people, pets, or valuable property. AirTags are not real-time GPS devices: nearby Apple
devices upload reports at an unpredictable cadence, and a fetched report can already be
old.

Apple's Find My reports are end-to-end encrypted. Signing in is not enough to decrypt an
AirTag. You must perform a one-time export of that AirTag's keys from a Mac that is signed
in to the owning Apple Account. Treat the exported file like a password: anyone with it
and a suitable Apple session may be able to query the tag's reports.

The Apple password is used only during interactive setup or reauthentication. The
integration removes it from the saved account state before writing the Home Assistant
config entry. Session tokens and AirTag key material are necessarily stored in Home
Assistant's `.storage` data, so protect and back up that directory appropriately.

## Obtain the AirTag key file

On a compatible Mac where Find My can see the AirTag:

```bash
python3 -m venv findmy-export
source findmy-export/bin/activate
pip install 'FindMy==0.10.2'
python3 -m findmy decrypt --out-dir devices/
```

The final command opens an interactive macOS keychain prompt and therefore cannot be run
over SSH. It writes one JSON file per Find My accessory. macOS 15 may require the
`beaconstorekey-extractor` process documented by FindMy.py. macOS 26 currently prevents
the required key export; consult the current FindMy.py documentation before changing
security settings. Re-enable System Integrity Protection if an extraction procedure asks
you to disable it temporarily.

## Install and configure

### HACS

HACS cannot access private GitHub repositories. While this repository is private, use the
manual installation below. If the repository is later made public:

1. Open HACS and select **Custom repositories**.
2. Add `https://github.com/kayloehmann/ha-airtag-tracker` as category **Integration**.
3. Install **AirTag Tracker** and restart Home Assistant.

### Manual installation

1. Download or clone this repository.
2. Copy `custom_components/airtag_tracker` into Home Assistant's
   `/config/custom_components/` directory.
3. Restart Home Assistant.

### Configuration

1. Open **Settings → Devices & services → Add integration → AirTag Tracker**.
2. Enter the Apple Account credentials and complete Apple's two-factor prompt.
3. Upload the JSON file for the AirTag.
4. Open the integration's options to adjust the inside/outside polling intervals.

The first lookup can take substantially longer than later lookups while FindMy.py aligns
the AirTag's rolling keys. The integration persists the resulting alignment state.

## Automation examples

Notify when an AirTag leaves all configured zones and the underlying report is reasonably
fresh:

```yaml
automation:
  - alias: "Tracked item left known zones"
    triggers:
      - trigger: state
        entity_id: device_tracker.tracked_item
        to: not_home
    conditions:
      - condition: numeric_state
        entity_id: sensor.tracked_item_report_age
        below: 900
    actions:
      - action: notify.mobile_app_your_phone
        data:
          title: "AirTag location"
          message: "The tracked item left all known zones."
```

Flag stale data rather than mistaking an old report for a current position:

```yaml
automation:
  - alias: "AirTag report is stale"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tracked_item_report_age
        above: 1800
    actions:
      - action: notify.mobile_app_your_phone
        data:
          message: "The AirTag has not produced a fresh report for 30 minutes."
```

## Privacy and security

- Use a dedicated Apple Account if practical, and enable two-factor authentication.
- Never send the exported AirTag JSON, Home Assistant backup, or `.storage` files to
  anyone you do not trust.
- Location data is highly sensitive. Limit dashboard and automation access to the people
  who need it.
- Follow applicable law and obtain any consent required for the way the tracker is used.

## Credits

Cloud authentication, rolling-key alignment, report retrieval, and decryption are
provided by the MIT-licensed [FindMy.py](https://github.com/malmeloo/FindMy.py) project.

The integration itself is distributed under the [MIT License](LICENSE).
