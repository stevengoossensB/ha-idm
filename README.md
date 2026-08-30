# IDM for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Home Assistant integration for **[Mijn IDM](https://www.mijnidm.be)**, the customer portal of
[IDM](https://www.idm.be) — the Belgian intermunicipal waste company serving Lokeren and
surrounding municipalities.

It brings your **DIFTAR** data into Home Assistant: what each bin weighed when it was emptied,
what it cost, how much residual waste your household produces per year, and how that compares to
the average household of the same size in the IDM area. It also adds a **collection calendar**,
resolved automatically from your address.

Inspired by, and structurally modelled on, [geertmeersman/miwa](https://github.com/geertmeersman/miwa).

> This is an unofficial, community-built integration. It is not affiliated with or endorsed by IDM.

---

## What you get

The integration creates one device per linked address, plus one for your account.

### Kerbside emptyings (DIFTAR)

| Sensor | Unit | Notes |
| --- | --- | --- |
| `Totaal gewicht ledigingen` | kg | Full history, `total_increasing` so it feeds long-term statistics |
| `Totale kost ledigingen` | € | Full history |
| `<FRACTIE> laatste lediging` | kg | One per fraction (REST, GFT, …) |
| `<FRACTIE> laatste lediging datum` | timestamp | Handy for "bin was emptied today" automations |
| `<FRACTIE> laatste lediging kost` | € | |
| `<FRACTIE> kost <jaar>` | € | Cost per fraction for the running year |
| `Totale kost <jaar>` | € | All fractions, running year |

Each emptying sensor carries the barcode, volume, unit price and service cost as attributes.

### Residual waste benchmark

| Sensor | Unit | Notes |
| --- | --- | --- |
| `Restafval <jaar>` | kg | Your household's residual waste this year |
| `Restafval gemiddelde gezin <jaar>` | kg | IDM average for a household of your size |
| `Restafval t.o.v. gemiddelde <jaar>` | % | Under 100 % means you produce less than average |
| `Aantal gezinsleden` | count | Household size as registered with IDM |

### Recycling centre

| Sensor | Unit | Notes |
| --- | --- | --- |
| `Recyclagepark gewicht <jaar>` | kg | Per-fraction breakdown in the attributes |
| `Recyclagepark kost <jaar>` | € | |
| `Laatste recyclageparkbezoek` | timestamp | |
| `Volgende recyclagepark reservatie` | timestamp | |
| `Geplande recyclagepark reservaties` | count | |

### Other

`Totale kost ondergrondse stortingen` and `Totale kost afval op afroep` are created when your
account has those services. Sensors are only created for the permissions your account actually
carries, so you will not see empty entities for services you do not use.

---

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/stevengoossens/ha-idm` as an **Integration**
3. Install **IDM**, then restart Home Assistant

### Manual

Copy `custom_components/idm` into your `config/custom_components/` directory and restart.

## Configuration

**Settings → Devices & Services → Add Integration → IDM**, then sign in with the email address and
password you use on [mijnidm.be](https://www.mijnidm.be).

Credentials are stored in your Home Assistant config entry and are only ever sent to
`www.mijnidm.be`. The portal is polled every 30 minutes — DIFTAR weighings appear a day or two
after collection, so there is nothing to gain from polling faster.

---

## Collection calendar

IDM does not serve the collection calendar from its portal — `idm.be/afvalkalender` embeds
**[Recycle!](https://recycleapp.be)** (Fost Plus). This integration talks to Recycle!'s public
API directly and **resolves your address automatically** from what the IDM portal already
reports, so there is nothing extra to configure.

| Entity | Type | Notes |
| --- | --- | --- |
| `calendar.idm_<id>_ophaalkalender` | calendar | All-day event per collection, 12 weeks ahead |
| `Volgende ophaling` | timestamp | Next collection of any fraction; `fracties` attribute lists everything collected that day |
| `Volgende ophaling <fractie>` | timestamp | One per fraction (Restafval, GFT, PMD, Papier-karton, …) |

Recycle! is a separate service from the IDM portal, so if it is unreachable the calendar entities
are simply not created and the DIFTAR sensors carry on unaffected.

If you would rather not have a second API in the mix, [olibos/HomeAssistant-RecycleApp](https://github.com/olibos/HomeAssistant-RecycleApp)
is a fuller standalone Recycle! integration (recycling park opening hours, per-fraction icons).

---

## Example automation

Notify when the residual bin has been weighed:

```yaml
automation:
  - alias: "REST bin emptied"
    triggers:
      - trigger: state
        entity_id: sensor.idm_<address_id>_laatste_lediging_datum_rest
    actions:
      - action: notify.mobile_app
        data:
          message: >
            Restafval opgehaald:
            {{ states('sensor.idm_<address_id>_laatste_lediging_rest') }} kg voor
            €{{ states('sensor.idm_<address_id>_laatste_lediging_kost_rest') }}
```

## How it works

The Mijn IDM portal is a Laravel application rendered with [Inertia.js](https://inertiajs.com):
every page embeds its full state as JSON in the `data-page` attribute of `<div id="app">`. The
client logs in with a normal session (`GET /login` for the CSRF token, then `POST /login`) and
reads the props from the same URLs a browser would request. There is no public API.

Money and weights come back as decimal strings already in EUR and kg — unlike some sibling
portals that return integer cents and grams — so no scaling is applied.

Your national registration number appears in the portal's address payload; it is filtered out
before anything reaches the logs or entity attributes.

## Debugging

Settings → Devices & Services → IDM → ⋮ → **Enable debug logging**, or:

```yaml
logger:
  default: warning
  logs:
    custom_components.idm: debug
```

## License

MIT
