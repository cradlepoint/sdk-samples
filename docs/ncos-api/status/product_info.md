# status/product_info

<!-- path: status/product_info -->
<!-- type: status -->
<!-- response: object -->

[status](../) / product_info

---

Product identity: model, MAC, company, features.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `mac0` | string | Primary MAC address |
| `company_name` | string | Manufacturer |
| `company_url` | string | Company URL |
| `product_name` | string | Model (e.g. E3000-C18B) |
| `copyright` | string | Copyright |
| `soc_serial` | string | SoC serial |
| `features` | array | Enabled feature flags |
| `has_activation_key` | boolean | Activation key present |
| `activation_key_verify` | object | See sub-table |
| `manufacturing` | object | See sub-table |

**activation_key_verify**

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | Activation key UUID |
| `matches` | boolean | Key matches |

**manufacturing**

| Field | Type | Description |
|-------|------|-------------|
| `board_ID` | string | Board identifier |
| `mftr_date` | string | Manufacture date |
| `serial_num` | string | Serial number |

### SDK Example
```python
import cp
info = cp.get('status/product_info')
if info:
    cp.log(f'{info.get("product_name")} MAC={info.get("mac0")}')
```

### REST
```
GET /api/status/product_info
```
