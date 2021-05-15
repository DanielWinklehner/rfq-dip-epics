import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';

import FaradayCup from "./Utils/FaradayCup.js"
import PowerSupply from "./Utils/PowerSupply.js"
import TimeStampGraph from './Utils/TimeStampGraph.js';
import NamedButton from './Utils/NamedButton.js';
import Beamline from './Utils/Beamline.js'

import {FaradayCups} from './Devices.js';

const PowerSupplies = [
  {macros: {'$(device)':'AU-20P7-1'}, vol_set: 'pva://$(device):voltage:set', cur_set: 'pva://$(device):current:set', vol_read: 'pva://$(device):voltage:read', cur_read: 'pva://$(device):current:read', button: 'pva://$(device):status:set', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Source'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Quadrapole 1'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Puller'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Dipole'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Einzel Lens'},
  {macros: {'$(device)':'testIOC'}, vol_set: 'pva://$(device):amplitude', cur_set: 'pva://$(device):amplitude', vol_read: 'pva://$(device):amplitude', cur_read: 'pva://$(device):amplitude', button: 'pva://$(device):BO1', vol_set_label: 'Voltage set', cur_set_label: 'Current set', vol_read_label: 'Voltage read', cur_read_label: 'Current read', prec: 2, title:'Quadrapole 2'},
]

class BeamlinePage extends React.Component {
  constructor(props){
    super(props);
    this.state = {FaradayCups: FaradayCups, PowerSupplies: PowerSupplies};
  }
  render() {
    return (
      <div>
        <Grid container xs={12} sm={12} style={{"justify-content":"center"}}>
          <Grid item>
            <Beamline/>
          </Grid>
        </Grid>
        <Grid container style={{marginTop:'8vh', "justify-content":"space-around"}}>
        <TimeStampGraph legends = {['Power Supply 1']} pvs={['pva://testIOC:amplitude']} yUnits='V' height="15vw" width="30vw"/>
        <TimeStampGraph legends = {['Power Supply 2']} pvs={['pva://testIOC:amplitude']} yUnits='V' height="15vw" width="30vw"/>
        <TimeStampGraph legends = {['Power Supply 3']} pvs={['pva://testIOC:amplitude']} yUnits='V' height="15vw" width="30vw"/>
        </Grid>
        <Grid container spacing={1} style={{display: "flex"}}>
          <Grid item container spacing={1} className={"Power supplies"} xs={12} sm={8}>
            {
            this.state.PowerSupplies.map(ps => (
              <Grid item sm={6}>
                <PowerSupply {...ps}/>
              </Grid>
            ))
            }
          </Grid>
          <Grid item container spacing={1} className={"FCs"} xs={12} sm={3} style={{"align-content":"flex-start"}}>
            {
              this.state.FaradayCups.map(fc => (
                <Grid item sm={12}><FaradayCup {...fc}/></Grid>
              ))
            }
            {
              this.state.FaradayCups.map(fc => (
                <Grid item sm={12}><FaradayCup {...fc}/></Grid>
              ))
            }
          </Grid>

        </Grid>
      </div>
    )
  }
}

BeamlinePage.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default BeamlinePage;