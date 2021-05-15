const PowerSupplies = [
  {macros: {'$(device)':'AU-20P7-1'}, vol_set: 'pva://$(device):voltage:set', cur_set: 'pva://$(device):current:set', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Source'},
  {macros: {'$(device)':'AU-20P7-2'}, vol_set: 'pva://$(device):voltage:set', cur_set: 'pva://$(device):current:set', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Filament Heating'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Puller'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Filament Voltage'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Einzel Lens'},
]

const TempSensors = [
  {macros: {'$(device)':'AU-20P7-1'}, pv: 'pva://$(device):voltage:set', prec: 2, legend:'Temp Sensor 1'},
  {macros: {'$(device)':'AU-20P7-1'}, pv: 'pva://$(device):voltage:set', prec: 2, legend:'Temp Sensor 2'},
  {macros: {'$(device)':'AU-20P7-1'}, pv: 'pva://$(device):voltage:set', prec: 2, legend:'Temp Sensor 3'},
  {macros: {'$(device)':'AU-20P7-1'}, pv: 'pva://$(device):voltage:set', prec: 2, legend:'Temp Sensor 4'},
]

const MassFlowControllers = [
  {macros: {'$(device)':'testIOC'}, drive_level: 'pva://$(device):amplitude', set_point_read: 'pva://$(device):amplitude', set_point_input: 'pva://$(device):amplitude', flow_rate: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Mass Flow Controller', prec: 2, drive_level_label: 'Drive Level', set_point_read_label: 'Set Point Read', set_point_input_label: 'Set Point Input', flow_rate_label: 'Flow rate'},
]

const FaradayCups = [
  {macros: {'$(device)': 'testIOC'}, current: 'pva://$(device):amplitude', front_plate_current: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', legend: 'Faraday Cup', prec: 2, current_label: 'Current', front_plate_current_label: 'Front-Plate current'},
]

const Valves = [
  {macros: {'$(device)': 'testIOC'}, button: 'pva://$(device):BO1', legend: 'Vent Valve'},
  {macros: {'$(device)': 'testIOC'}, button: 'pva://$(device):BO1', legend: 'Foreline Valve'},
  {macros: {'$(device)': 'testIOC'}, button: 'pva://$(device):BO1', legend: 'Mass Flow Valve'},
  {macros: {'$(device)': 'testIOC'}, button: 'pva://$(device):BO1', legend: 'Source-Body Valve'},
]

const IonGaugeControllers = [
  {macros: {'$(device)': 'testIOC'}, apg: 'pva://$(device):amplitude', diag_box: 'pva://$(device):amplitude', naim: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', apg_label: 'APG Pressure', diag_box_label: 'Diagnostic Box Pressure', naim_label: 'nAIM-S Ion Gauge Source Pressure', legend: 'Ion Gauge Controller', prec: 2},
]

const Interlocks = [
  {macros: {'$(device)': 'testIOC'}, pv: 'pva://$(device):BO1', label: 'HV Door Upper', onColor: 'green', offColor: 'red'},
  {macros: {'$(device)': 'testIOC'}, pv: 'pva://$(device):BO1', label: 'HV Door Lower', onColor: 'green', offColor: 'red'},
]

const WaterFlowControllers = [
  {macros: {'$(device)': 'testIOC'}, read1: 'pva://$(device):amplitude', read2: 'pva://$(device):amplitude', read3: 'pva://$(device):amplitude', read4: 'pva://$(device):amplitude', read1_label: 'Backplate', read2_label: 'Turbo pump', read3_label: 'Source Body', read4_label: 'Water flow', legend:'Water Flow Controller', prec: 2}
]

export {PowerSupplies, TempSensors, MassFlowControllers, FaradayCups, Valves, IonGaugeControllers, Interlocks, WaterFlowControllers};