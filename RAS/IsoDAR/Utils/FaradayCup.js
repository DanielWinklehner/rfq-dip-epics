import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';


import TextInput from '../../BaseComponents/TextInput';
import TextOutput from '../../BaseComponents/TextOutput';
import ToggleButton from '../../BaseComponents/ToggleButton';

class FaradayCup extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <fieldset>
        <legend style={{"padding":"3px 6px"}}>{this.props.legend}</legend>
        <Grid container spacing={1}  direction="row"  justify="flex-start"  alignItems="center" style={{display: "inline-flex", "flex-wrap":"nowrap"}}>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.current} macros={this.props.macros} label={this.props.current_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.front_plate_current} macros={this.props.macros} label={this.props.front_plate_current_label} alarmSensitive={true}/></Grid>
          <Grid item><ToggleButton pv={this.props.button} macros={this.props.macros}/></Grid>
        </Grid>
        </fieldset>
      </>
      )
  }
}

export default FaradayCup;