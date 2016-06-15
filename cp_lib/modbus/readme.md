# directory: ./cp_lib/modbus
## Simplistic transaction parsing for Modbis

These files allow simple conversion between Modbus/TCP, Modbus/RTU, and Modbus/ASCII.

This is actually pretty easy, as they all enclose the same "ADU" message. For example, the block read of 10 coils starting at the 2nd (data[1]) offset is:

* Modbus/RTU = b'**\x01\x01\x00\x01\x00\x0A**\x44\x2A'
* Modbus/ASCII = b':**01010001000A**66\r\n'
* Modbus/TCP = b'\x00\xA5\x00\x00\x00\x06**\x01\x01\x00\x01\x00\x0A**'

Notice that they all include the 6-byte value **01 01 00 01 00 0A**! So conversion is very mechanical.

## File: __init__.py

Empty - exists to define cp_lib/modbus as a module.

## File: transaction.py ##

Defines a class IaTransaction(), which supports splitting up a request and releated response, plus some timing and routing details.

*Unit testing is in test/test\_cplib\_modbus\_trans\_modbus.py*

## File: transaction\_modbus.py ##

Subclasses IaTransaction() as ModbusTransaction(). 

You can use as follows:

* create the ModbusTransaction()
* call obj.set\_request(data, 'mbtcp'), which causes the Modbus/TCP request to be parsed into the raw Modbus/ADU format.
* call obj.get\_request(data, 'mbrtu'), which causes the raw Modbus/ADU data to be recombined to be Modbus/RTU.

The set\_response()/get\_response() work in the same manners, so obj.set\_response(data, 'mbrtu') would break up the RTU response, and obj.get\_response(data, 'mbtcp') would reform as Modbus/TCP, including the correct header adjustments.

*Unit testing is in test/test\_cplib\_modbus\_trans\_modbus.py*

## File: modbus\_asc.py ## 

The checksum, encode/decode, and end-of-message routines for Modbus/ASCII.

*Unit testing is in test/test\_cplib\_modbus\_asc.py* 

## File: modbus\_rtu.py ##

The checksum, encode/decode, and end-of-message routines for Modbus/RTU. Since RTU lacks any formal 'length' test, it also includes routines to estimate size based on Modbus command form.

*Unit testing is in test/test\_cplib\_modbus\_rtu.py* 

## File: modbus\_tcp.py ##

The checksum, encode/decode, and end-of-message routines for Modbus/TCP.

*Unit testing is in test/test\_cplib\_modbus\_tcp.py*