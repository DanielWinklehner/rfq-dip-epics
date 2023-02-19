import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@mui/material/Grid';
import Tank from '../../BaseComponents/Tank';

class TempSensor extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        
        <fieldset>
        <legend>{this.props.legend}</legend>
          <Tank pv={this.props.pv} macros={this.props.macros}  prec={this.props.macros} max={500} min={0} alarmSensitive={true} units={'C'} width={105} lockAspectRatio={false} height={150}/>
        </fieldset>
      </>
      )
  }
}

export default TempSensor;
