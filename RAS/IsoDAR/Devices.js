const PowerSupplies = [
  {macros: {'$(device)':'AU-20P7-1'}, vol_set: 'pva://$(device):voltage:setpoint', cur_set: 'pva://$(device):current:setpoint', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', button_enable: 'pva://$(device):enable', button_disable: 'pva://$(device):disable', button_reset: 'pva://$(device):reset', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Source'},
  {macros: {'$(device)':'AU-20P7-2'}, vol_set: 'pva://$(device):voltage:setpoint', cur_set: 'pva://$(device):current:setpoint', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', button_enable: 'pva://$(device):enable', button_disable: 'pva://$(device):disable', button_reset: 'pva://$(device):reset', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Puller'},
  {macros: {'$(device)':'AU-20P7-3'}, vol_set: 'pva://$(device):voltage:setpoint', cur_set: 'pva://$(device):current:setpoint', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', button_enable: 'pva://$(device):enable', button_disable: 'pva://$(device):disable', button_reset: 'pva://$(device):reset', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Lens 1'},
  {macros: {'$(device)':'AU-20P7-4'}, vol_set: 'pva://$(device):voltage:setpoint', cur_set: 'pva://$(device):current:setpoint', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', button_enable: 'pva://$(device):enable', button_disable: 'pva://$(device):disable', button_reset: 'pva://$(device):reset', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Lens 3'},

  // {macros: {'$(device)':'abc'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Puller'},
  {macros: {'$(device)':'REK'}, vol_set: 'pva://$(device):voltage:setpoint', cur_set: 'pva://$(device):current:setpoint', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Filament Discharge'},
  {macros: {'$(device)':'TDK'}, vol_set: 'pva://$(device):voltage:setpoint', cur_set: 'pva://$(device):current:setpoint', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Filament Heating'},
]

const TempSensors = [
  {macros: {'$(device)':'THM'}, pv: 'pva://$(device):t1:gettemp', prec: 2, legend:'Temp Sensor 1'},
  {macros: {'$(device)':'THM'}, pv: 'pva://$(device):t2:gettemp', prec: 2, legend:'Back Plate Temp'},
  {macros: {'$(device)':'THM'}, pv: 'pva://$(device):t3:gettemp', prec: 2, legend:'Magnet Plate Temp'},
  {macros: {'$(device)':'THM'}, pv: 'pva://$(device):t4:gettemp', prec: 2, legend:'Temp Sensor 4'},
]

const MassFlowControllers = [
  {macros: {'$(device)':'MFC'}, drive_level: 'pva://$(device):amplitude', set_point_read: 'pva://$(device):getSP', set_point_input: 'pva://$(device):setSP', flow_rate: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Mass Flow Controller', prec: 2, drive_level_label: 'Drive Level', set_point_read_label: 'Set Point Read', set_point_input_label: 'Set Point Input', flow_rate_label: 'Flow rate'},
]

const FaradayCups = [
  // {macros: {'$(device)': 'abc'}, current: 'pva://$(device):amplitude', front_plate_current: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Faraday Cup DB1', prec: 2, current_label: 'Current', front_plate_current_label: 'Front-Plate current'},
  // {macros: {'$(device)': 'abc'}, current: 'pva://$(device):amplitude', front_plate_current: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Faraday Cup DB2', prec: 2, current_label: 'Current', front_plate_current_label: 'Front-Plate current', no_button:1},
]

const Valves = [
  {macros: {'$(device)': 'VALVE'}, button: 'pva://$(device):s1:set', legend: 'Foreline Valve'},
  {macros: {'$(device)': 'VALVE'}, button: 'pva://$(device):s2:set', legend: 'MFC Shutoff Valve'},
  {macros: {'$(device)': 'VALVE'}, button: 'pva://$(device):s3:set', legend: 'Vent Valve'},
  {macros: {'$(device)': 'VALVE'}, button: 'pva://$(device):s4:set', legend: 'Faraday Cup'},
]

const IonGaugeControllers = [
  {macros: {'$(device)': 'PRESSURE'}, apg: '$(device):apg:getpressure', diag_box: 'pva://$(device):diag_box:getpressure', naim: 'pva://AIM:getpressure', button: 'pva://AIM:enable', apg_label: 'APG Pressure', diag_box_label: 'Diagnostic Box Pressure', naim_label: 'nAIM-S Ion Gauge Source Pressure', legend: 'Ion Gauge Controller', prec: 2},
]

const Interlocks = [
  {macros: {'$(device)': 'INTLK'}, pv: 'pva://$(device):i1:get_interlock', label: 'HV Door Lower', onColor: 'green', offColor: 'red'},
  {macros: {'$(device)': 'INTLK'}, pv: 'pva://$(device):i2:get_interlock', label: 'HV Door Upper', onColor: 'green', offColor: 'red'},
]

const WaterFlowControllers = [
  {macros: {'$(device)': 'SENSOR'}, read1: 'pva://$(device):f1:getflow', read2: 'pva://$(device):f2:getflow', read3: 'pva://$(device):f3:getflow', read4: 'pva://$(device):f4:getflow', read5: 'pva://$(device):f5:getflow', read1_label: 'N/A', read2_label: 'Turbo pump', read3_label: 'Front Plate', read4_label: 'Faraday Cup 1', read5_label: 'N/A', legend:'Water Flow Controller', prec: 2}
]

export {PowerSupplies, TempSensors, MassFlowControllers, FaradayCups, Valves, IonGaugeControllers, Interlocks, WaterFlowControllers};
