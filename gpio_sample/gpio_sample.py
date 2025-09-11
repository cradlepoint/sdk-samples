# Ericsson Cradlepoint SDK Application
import cp
cp.log('Starting...')
gpios = cp.get_available_gpios()
cp.log(f'gpios: {gpios}')
for gpio in gpios:
    cp.log(f'gpio: {gpio}')
    cp.log(f'gpio value: {cp.get_gpio(gpio)}')
