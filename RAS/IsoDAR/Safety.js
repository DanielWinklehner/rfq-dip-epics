import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';

import TimeStampGraph from './Utils/TimeStampGraph.js';
import TempSensor from './Utils/TempSensor.js'
import IonGaugeController from "./Utils/IonGaugeController.js"

import {Interlocks, WaterFlowControllers, TempSensors, IonGaugeControllers} from './Devices.js';
import Indicator from './Utils/Indicator.js';
import WaterFlowController from './Utils/WaterFlowController.js';
import "./Home.css"


class Safety extends React.Component {
  constructor(props){
    super(props);
    this.state = {Interlocks: Interlocks, WaterFlowControllers: WaterFlowControllers, TempSensors: TempSensors, IonGaugeControllers: IonGaugeControllers};
  }
  render() {
    return (
      <div>
        <Grid container style={{"justify-content":"center"}}>
          <Grid item container spacing={0} style={{"width":"fit-content", "height":"fit-content"}}>
            <fieldset>
            <legend>HV Interlocks</legend>
            <Grid container spacing={3} style={{"flex-direction":"column"}}>
            {
              this.state.Interlocks.map(il => (
                <Grid item style={{"width":"fit-content"}}><Indicator {...il}/></Grid>
              ))
            }
            </Grid>
            </fieldset>
          </Grid>

          <Grid item container style={{"width":"fit-content", "height":"fit-content"}}>
            {
              this.state.WaterFlowControllers.map(wfc => (
                <Grid item><WaterFlowController {...wfc}/></Grid>
              ))
            }
          </Grid>
          
          <Grid item container className={"Temperature sensors"} xs={12} sm={4} style={{"justify-content":"space-around", "width":"fit-content"}}>
            {
              this.state.TempSensors.map(ts => (
                <Grid item sm={3} xs={12}><TempSensor {...ts}/></Grid>
              )) 
            }
          </Grid>
          {/* <Grid item container style={{"width":"fit-content"}}>
            {
              this.state.FaradayCups.map(fc => (
                <Grid item><FaradayCup {...fc}/></Grid>
              ))
            }
          </Grid> */}
          
          <Grid item container style={{"width":"fit-content"}}>
            {
              this.state.IonGaugeControllers.map(ioc => (
                <Grid item><IonGaugeController {...ioc}/></Grid>
              ))
            }

          </Grid>
        </Grid>

        <Grid container style={{"justify-content":"space-around", "margin-top":"2em"}}>
        
          <Grid item>
            <TimeStampGraph legends={['Backplate', 'Turbo pump', 'Source body', 'Water flow']} pvs={['pva://testIOC:amplitude', 'pva://testIOC:amplitude', 'pva://testIOC:amplitude', 'pva://testIOC:amplitude']} yUnits='V' height="20vw" width="30vw"/>
          </Grid>
          <Grid item>
            <TimeStampGraph legends={['APG Pressure', 'DB Pressure', 'Source body', 'nAIM-S IGS Pressure']} pvs={['pva://avr6:apg:getpressure', 'pva://avr6:diag_box:getpressure', 'pva://testIOC:amplitude', 'pva://testIOC:amplitude']} yUnits='torr' height="20vw" width="30vw"/>
          </Grid>

        </Grid>

      </div>
    )
  }
}

Safety.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default Safety;
