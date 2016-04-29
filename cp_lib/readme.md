# Lynn's Sample Design

Any sample in the system must be created from a sample template. Example templates:

- Single Temperature Value, with Deg F as unit of measure
- An average Temperature, with an attached time period - such as the average temperature in degree F for the hour from 
2:00PM to 2:59PM
- The min/max/avg Temperature, with an attached time period
- The temperatures can be define as +/- 0.5 (so like 70 F only), or like +/- 0.1 (so like 70.2 F), which allows more 
accurate packing for transport as XML or JSON.

This allows more flexible samples data, for example the template can include the ability to convert deg C to deg F. 
Assuming the sample includes a reference to the template (instead of the units string), the individual instance 
samples are no larger than the old DIA form
 
# Files:

## DataCore
data_core.py holds the base object, and is the tree/handle node for the object. It has no real data, but does include the child/tree structures. It includes attributes:

- [**data\_name**]: str, is the NON-unique name for this object - example 'level' or 'outdoor', which may be used by other objects
- [**class**]: str, defines how the object can be processed
- [**index**]: int, a simple unique counting number, but the value MAY vary between runs. Technically, it is the order the objects are created during the current run-time.
- [**path**]: str, is the unique name such as 'tank01.level'
- **PATH_SEP**:str, is the symbol used within the path. Default is '.' to avoid the special meanings of a '/' or '\'.
- [**role**]: str, is a subset of 'class', allowing shared processing handlers

Special internal values include:

- **\_parent**: DataCore, handle of my parent instance
- **\_children\_list**: list, an unordered list of DataCore objects
- **\_children\_keyed**: dict, keyed on the data_name, so for example in the path example above, the node 'tank01' would have a child named 'level' 
- **\_private**: bool, if True, then this is an internal hidden node
- **\_template**: None or DataTemplate reference, is a special shared handler used to, for example, allow a dozen data objects to 'share' data validation and/or alarm processing.
 
## DataObject
data_object.py holds the next higher level of data, which are constrained to a specific list of types, including:

- **base**: *DataObject*, with no data, but might be a parent/container for children. For example a 'tank' may have no data, as one needs to look at the 'level' or 'empty_alert' children.
- **string**: *StringObject* with a user-friendly UTF8 string value, with no other encoding or meaning. For example, a 'tank' may have a contents such as 'aviation fuel grade 2'.
- **digital**: *BooleanObject* is a True/False object with optional alarm handling.
- **analog**: *NumericObject* is a float which may include optional precision filters to force to int or X.0, etc. There is no true in, since most (all?) system input/output shall be JSON, which has a common 'numeric'.
- **gps**: *GpsObject* is a special case object, It rarely will be used by itself, but can be used to 'tag' data samples tied to a GPS locations, such as a police car's lightbar being turned True/On at a specific location and time.

A base DataObject has the common attributes shared by ALL the other DataObjects, including these static values:

- [**data\_name**]: *str*, is unique to the 'parent' collection of children. This may NOT the same name as the DataCore's ['data_name']. It is 'indexable', so not UTF8.
- [**display\_name**]: *UTF8*, user-defined display name, without constraints or rules.
- [**description**]: *UTF8*, user-defined descriptive string, without constraints or rules.
- [**display\_color**]: DataColor, has no value in Router, but can be used to manage font & back ground color in simple web or UI displays. The DataColor  is a common HTML/CSS sRGB tuple 
- [**font\_size**]: float, a simple scaling in (50%, 75%, 100%, 125%, 150%). It is NOT intended to format web pages, but to compensate for UTF8 character sets which may appear unusually small or large on a traditional English-oriented UI.
- [**data\_type**]: str, selects the type, such as digital or analog.
- [**value\_type**]: type, Python info about the data value.
- [**failsafe**]: ??, the startup or fault value - a 'safe' value when the true value is unknown.
- [**attach\_gps**]: bool, T/F, if DataSample time-series data should have GPS info attached. Default is False, so do not attach.
- [**read\_only**]: bool, T/F, if DataObject should not change in real-time.

The following values may be dynamic:

- [**value**]: DataSample, None or the appropriate data value.
- [**source**]: ??, defines the source of non-read\_only data.
- [**owner\_token**]: str, a user-defined 'lock' to writing of new data values.
- [**health**]: float, 0-100% for data health.
 
## StringObject
See **StringAttributeHandler** in data_attribute.py. A StringObeject has no data attributes, but the [**value**] attribute will be a UTF8 user-friendly string. Many strings will be read\_only, however some might outputs from various real-time state machines such as "I/O is within expected range" or "I/O is wildly bad".

## DigitalObject
See **BooleanAttributeHandler** in data_attribute.py. A DigitalObeject adds the following attributes.

- [**display\_name\_true**]: *UTF8*, user-defined display 'tag' which matches [value] = True. For example, it might be 'normal', 'open', or 'snowing'.
- [**display\_name\_false**]: *UTF8*, like [display\_name\_true], but when [value] = False. For example, it might be 'too hot', 'closed', or 'sunny'.
- [**display\_color\_true**]: DataColor, how to display [value] when True. The DataColor  is a common HTML/CSS sRGB tuple, and perhaps the background should be white when True, and red when False. 
- [**display\_color\_false**]: DataColor, like [display\_color\_true], but when [value] is False. 
- [**invert**]: bool, T/F if any 'set' of [value] should be inverted. Default is False or not-present, so no inversion. 
- [**abnormal\_when**]: bool, when [value] matches this value, then based upon the application context, this data object is abnormal, in alarm, or not-as-desired. *Note that this does NOT drive alarms or alerts!* It is instead a HINT which helps a consuming-agent to understand good-verse-bad states. Default is False or not-present. 
- [**auto\_reset**]: bool, defines if 'repeated' data is new or old. For example, the source defines a new *restart = True* event, when the existing value is True. If auto\_reset is False (default), then the 'repeat' is treated as a redundant or refresh, so may not propagate. If auto\_reset is True, then the 'repeat' is treated as new data and propagated. 
- [**delay\_t\_f**]: numeric, seconds to delay (or debounce) a transition from True to False. For example, you might want a door-closed value = True to remain True unless the door is open longer than 10 seconds.
- [**delay\_f\_t**]: numeric, like [delay\_t\_f], but when [value] = False, delay going True.
- TBD - add time of last go-true and last go-false?

## NumericObject
See **NumericAttributeHandler** in data_attribute.py. A NumericObject adds the following attributes.

- [**uom**]: *UTF8*, user-defined unit-of-measure such as 'F' or 'miles'.
- TBD - add min/max/avg option?

## GpsObject
See **GpsAttributeHandler** in data_attribute.py. A GpsObject adds the following attributes (* TBD *). I am still considering. It needs to include the GPS health, as well as lat/long, possibly speed & others.

## DataTemplate
data_template.py holds shared objects for use with DataObjects and DataSamples. The template does 2 basic functions:

1. supplies a shared template, such as 'uom' (unit-of-measure) as Gallons for 10 different tank.level DataObjects and related DataSamples.
2. includes a process_value() function which validates a new data value is of the correct type, within permitted ranges, and rounded to a reasonable precision.

Each DataCore instance can contain a reference to a DataTemplate, although the values are usually copied out into the Data object. For example, if the template has a analog 'failsafe' of 999, this will be copied to the failsafe of a AnalogObject. This means changes to the Template may (TBD) need to manually updated in objects.

Each DataSample instance also can contain a reference to a DataTemple, and is generally treated as an active helper. For example, if the template has a 'uom' of 'F', this will be fetched on-demand to create a JSON record for export or display. This means changes to the Template automatically cause changes going forward - such as changign a temperature from 'F' to 'C'.

## DataSample
data_sample.py holds granular time-series data attached to a DataObject. For example, a DigitalObject named 'back\_door' might have a current status, which is False/'open', but it might also hold the last 10 times the door was opened or closed as a small history. These 10 values are called Data Samples, and include these attributes:

- [**value**] required, is the data value of an appropriate type, such as True or 73.45.
- [**timestamp**] required, is the UTC time() of the data recorded.
- [**quality**] optional, is a numeric bit-mask of status, such as disabled, low-alarm, go-abnormal, and so on. If missing, it is assumed quality is valid.
- **get_uom()** optional, and fetches a UTF8 string from a template. In a JSON sample this will be ['uom']. For Digital data, this will return the appropriate 'display_name_true' or 'display_name_false'. For string or GPS data, it returns None.
- **get_gps()** optional, and fetches ... something (TBD). Returns None if GPS data is not being attached, else it maybe a JSON sub-item or CSV. Format to TBD.
-  TBD - how to handle a **stats min/max/avg** value? Is it just a 3-item tuple?

## DataColor
data_color.py holds a standard HTML/CSS color or color-pair. Generally this is assumed to be what's called CSS3 (see [http://www.w3.org/TR/css3-color/](http://www.w3.org/TR/css3-color/ "CSS Color Module Level 3")). 

It uses the PyPi WebColors module, so can be set with far greater flexibility than I expected to be used! (see [http://pypi.python.org/pypi/webcolors/](http://pypi.python.org/pypi/webcolors/ "webcolors 1.5").

In general, it assumes the colors are set via string values, such as 'orchid' or '#da70d6'. Internally, the values will be retained as numeric, but you can fetch the vales as HEX strings, or as CSS3 names if there is a match. Given the flexibility of the Python webcolors module, it should be fairly easy to extend it to handle other notations like RGB percentages.

A DataColor value can be one of three things:

- **None**, which means no-effect or as default.
- a **single value**, which is assumed the BACKGROUND value, with the fore/font color remaining as default. So for example, a data value might have background colors of 'green', 'yellow', or 'red' based on an alarm status, always assuming the font remains default such as 'black'.
- a **2-value tuple**, which is assumed (BACKGROUND, FONTCOLOR) such as ('white','navy') for Navy blue text on a white background. 

The router generally ignores a DataColor, but it will be used for any local UI or when sent for remove UI display.

## DataSetting (TBD)
data_setting.py are special DataObjects which are intended to be saved and restored between runs.

## DataAlarm (TBD)
data_alarm.py are special filtering processors which validate changes in DataObjects.
