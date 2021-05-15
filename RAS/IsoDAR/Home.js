import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';
import TextField from '@material-ui/core/TextField';
import MenuItem from '@material-ui/core/MenuItem';

import Beamline from "./Utils/Beamline.js"
import PowerSupply from "./Utils/PowerSupply.js"
import TempSensor from "./Utils/TempSensor.js"
import MassFlowController from "./Utils/MassFlowController.js"
import IonGaugeController from "./Utils/IonGaugeController.js"
import FaradayCup from "./Utils/FaradayCup.js"
import NamedButton from './Utils/NamedButton.js';
import TimeStampGraph from './Utils/TimeStampGraph.js';


import './Home.css'
import emergency from './Media/emergency.png';
import {PowerSupplies, TempSensors, MassFlowControllers, FaradayCups, Valves, IonGaugeControllers} from './Devices.js';

class Home extends React.Component {
  constructor(props){
    super(props);
    this.state = {PowerSupplies: PowerSupplies, TempSensors: TempSensors, MassFlowControllers: MassFlowControllers, FaradayCups: FaradayCups, Valves: Valves, IonGaugeControllers: IonGaugeControllers};
  }
  render() {
    return (
      <div>
        <Grid container xs={12} sm={12} style={{"justify-content":"center"}}>
          <Grid item>
            <Beamline/>
          </Grid>
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
            {
            this.state.MassFlowControllers.map(ms => (
              <Grid item sm={6}><MassFlowController {...ms}/></Grid>
            ))

            }

          </Grid>

          <Grid item container className={"Temperature sensors"} xs={12} sm={4} style={{"justify-content":"space-around"}}>
            {
              this.state.TempSensors.map(ts => (
                <Grid item sm={3} xs={12}><TempSensor {...ts}/></Grid>
              )) 
            }
            {
              this.state.IonGaugeControllers.map(ioc => (
                <Grid item><IonGaugeController {...ioc}/></Grid>
              ))
            }

          </Grid>
        </Grid>

        <Grid container spacing={2} style={{"margin-top": "10px"}}>


          {/* <Grid item container xs={12} sm={4} className="fit-content">

          </Grid>


          <Grid item container xs={12} sm={4} className="fit-content">
          </Grid> */}
          
          <Grid item spacing={2} container xs={12} sm={8}>
            <TimeStampGraph legends = {['Graph 1']} pvs={['pva://testIOC:amplitude']} yUnits='V' width="50%" height="30vh"/>
            <TimeStampGraph legends = {['Graph 2']} pvs={['pva://testIOC:amplitude']} yUnits='A' width="50%" height="30vh"/>
          </Grid>

          <Grid container item spacing={2} xs={12} sm={4} style={{"align-items": "center", "position":"relative", "bottom":"1em"}}>
            {
              this.state.FaradayCups.map(fc => (
                <Grid item><FaradayCup {...fc}/></Grid>
              ))
            }

            <Grid item style={{"text-align-last":"center"}}><img src={emergency} width="60%" height="60%" /></Grid>
          </Grid>

        </Grid>
      </div>
      
    )
  }
}

Home.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default Home;