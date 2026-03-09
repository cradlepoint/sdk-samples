# status/signal_strength_leds

<!-- path: status/signal_strength_leds -->
<!-- type: status -->
<!-- response: string -->

[status](../) / signal_strength_leds

---

Signal strength LED state. `"on"` or `"off"`.

### SDK Example
```python
import cp
leds = cp.get('status/signal_strength_leds')
cp.log(f'Signal LEDs: {leds}')
```

### REST
```
GET /api/status/signal_strength_leds
```
