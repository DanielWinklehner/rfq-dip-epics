import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@mui/material/Grid';

import IonGaugeController from "./Utils/IonGaugeController.js"
import TimeStampGraph from './Utils/TimeStampGraph.js';
import NamedButton from './Utils/NamedButton.js';
import ToggleButton from '../BaseComponents/ToggleButton.js';

import {Valves, IonGaugeControllers} from './Devices.js';
import ModGraphY from './Utils/ModGraphY.js';

class Vacuum extends React.Component {
  constructor(props){
    super(props);
    this.state = {Valves: Valves, IonGaugeControllers: IonGaugeControllers};
  }
  render() {
    return (
      <div>
        {/* <Grid container style={{marginTop:'8vh', "justify-content":"space-between"}}>
        <ModGraphY legends = {['APG']} pvs={['pva://PRESSURE:apg:getpressure']} yUnits='torr' height="20vw" width="30vw"/>
        <ModGraphY legends = {['Diagnostic Box']} pvs={['pva://PRESSURE:diag_box:getpressure']} yUnits='torr' height="20vw" width="30vw"/>
        <ModGraphY legends = {['nAIM-S IGS']} pvs={['pva://AIM:getpressure']} yUnits='torr' height="20vw" width="30vw"/>
        </Grid> */}
        <Grid container style={{"justify-content":"center"}}>

          <Grid item container xs={12} sm={5} className="fit-content">
            {
              this.state.IonGaugeControllers.map(ioc => (
                <Grid item><IonGaugeController {...ioc}/></Grid>
              ))
            }
          </Grid>

          <Grid item container xs={12} sm={2} className="fit-content" style={{"height":"auto", "margin-top": "10px"}}>
              <fieldset>
              <legend>Valves</legend>
              {
                this.state.Valves.map(valve => (
                  <Grid item style={{"width":"100%"}}><NamedButton {...valve}/></Grid>
                ))
              }
              </fieldset>
          </Grid>
        </Grid>
      </div>
    )
  }
}

Vacuum.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default Vacuum;
