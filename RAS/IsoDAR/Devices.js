const PowerSupplies = [
  {macros: {'$(device)':'AU-20P7-1'}, vol_set: 'pva://$(device):voltage:set', cur_set: 'pva://$(device):current:set', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Source'},
  {macros: {'$(device)':'AU-20P7-2'}, vol_set: 'pva://$(device):voltage:set', cur_set: 'pva://$(device):current:set', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Filament Heating'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Puller'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Filament Voltage'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Einzel Lens'},
]

const TempSensors = [
  {macros: {'$(device)':'avr10'}, pv: 'pva://$(device):t2:gettemp', prec: 2, legend:'Back Plate Temp'},
  {macros: {'$(device)':'avr10'}, pv: 'pva://$(device):t3:gettemp', prec: 2, legend:'Magnet Plate Temp'},
  {macros: {'$(device)':'abc'}, pv: 'pva://$(device):voltage:set', prec: 2, legend:'Temp Sensor 3'},
  {macros: {'$(device)':'abc'}, pv: 'pva://$(device):voltage:set', prec: 2, legend:'Temp Sensor 4'},
]

const MassFlowControllers = [
  {macros: {'$(device)':'testIOC'}, drive_level: 'pva://$(device):amplitude', set_point_read: 'pva://$(device):amplitude', set_point_input: 'pva://$(device):amplitude', flow_rate: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Mass Flow Controller', prec: 2, drive_level_label: 'Drive Level', set_point_read_label: 'Set Point Read', set_point_input_label: 'Set Point Input', flow_rate_label: 'Flow rate'},
]

const FaradayCups = [
  {macros: {'$(device)': 'testIOC'}, current: 'pva://$(device):amplitude', front_plate_current: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Faraday Cup DB1', prec: 2, current_label: 'Current', front_plate_current_label: 'Front-Plate current'},
  {macros: {'$(device)': 'testIOC'}, current: 'pva://$(device):amplitude', front_plate_current: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Faraday Cup DB2', prec: 2, current_label: 'Current', front_plate_current_label: 'Front-Plate current', no_button:1},
]

const Valves = [
  {macros: {'$(device)': 'avr12'}, button: 'pva://$(device):s1:set', legend: 'Foreline Valve'},
  {macros: {'$(device)': 'avr12'}, button: 'pva://$(device):s2:set', legend: 'MFC Shutoff Valve'},
  {macros: {'$(device)': 'avr12'}, button: 'pva://$(device):s3:set', legend: 'Vent Valve'},
  {macros: {'$(device)': 'avr12'}, button: 'pva://$(device):s4:set', legend: 'Faraday Cup'},
]

const IonGaugeControllers = [
  {macros: {'$(device)': 'avr6'}, apg: 'pva://$(device):apg:getpressure', diag_box: 'pva://$(device):diag_box:getpressure', naim: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', apg_label: 'APG Pressure', diag_box_label: 'Diagnostic Box Pressure', naim_label: 'nAIM-S Ion Gauge Source Pressure', legend: 'Ion Gauge Controller', prec: 2},
]

const Interlocks = [
  {macros: {'$(device)': 'avr11'}, pv: 'pva://$(device):i1:get_interlock', label: 'HV Door Upper', onColor: 'green', offColor: 'red'},
  {macros: {'$(device)': 'avr11'}, pv: 'pva://$(device):i2:get_interlock', label: 'HV Door Lower', onColor: 'green', offColor: 'red'},
]

const WaterFlowControllers = [
  {macros: {'$(device)': 'avr10'}, read1: 'pva://$(device):f1:getflow', read2: 'pva://$(device):f2:getflow', read3: 'pva://$(device):f3:getflow', read4: 'pva://$(device):f4:getflow', read1_label: 'Backplate', read2_label: 'Turbo pump', read3_label: 'Source Body', read4_label: 'Water flow', legend:'Water Flow Controller', prec: 2}
]

export {PowerSupplies, TempSensors, MassFlowControllers, FaradayCups, Valves, IonGaugeControllers, Interlocks, WaterFlowControllers};
