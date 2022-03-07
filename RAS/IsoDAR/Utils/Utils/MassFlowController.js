import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';


import TextInput from '../../BaseComponents/TextInput';
import TextOutput from '../../BaseComponents/TextOutput';
import ToggleButton from '../../BaseComponents/ToggleButton';

class MassFlowController extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <fieldset>
        <legend style={{"padding":"3px 6px"}}>{this.props.legend}</legend>
        <Grid container spacing={1}  direction="row"  justify="flex-start"  alignItems="center" style={{display: "inline-flex", "flex-wrap":"nowrap"}}>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.drive_level} macros={this.props.macros} label={this.props.drive_level_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.set_point_read} macros={this.props.macros} label={this.props.set_point_read_label} alarmSensitive={true}/></Grid>
          <Grid item><TextInput prec={this.props.prec} pv={this.props.set_point_input} macros={this.props.macros} label={this.props.set_point_input_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.flow_rate} macros={this.props.macros} label={this.props.flow_rate_label} alarmSensitive={true}/></Grid>
          <Grid item><ToggleButton pv={this.props.button} macros={this.props.macros}/></Grid>
        </Grid>
        </fieldset>
      </>
      )
  }
}

export default MassFlowController;