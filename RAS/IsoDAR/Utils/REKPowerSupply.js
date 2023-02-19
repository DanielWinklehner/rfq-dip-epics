import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@mui/material/Grid';


import TextInput from '../../BaseComponents/TextInput';
import TextOutput from '../../BaseComponents/TextOutput';
import ToggleButton from '../../BaseComponents/ToggleButton';

class PowerSupply extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <fieldset style={{"height":"auto"}}>
        <legend style={{"padding":"3px 6px"}}>{this.props.title}</legend>
        <Grid container spacing={1}  direction="row"  justify="flex-start"  alignItems="center" style={{display: "inline-flex", "flex-wrap":"nowrap"}}>
          <Grid item><TextInput prec={this.props.prec} pv={this.props.vol_set} macros={this.props.macros} label={this.props.vol_set_label} alarmSensitive={true}/></Grid>
          <Grid item><TextInput prec={this.props.prec} pv={this.props.cur_set} macros={this.props.macros} label={this.props.cur_set_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.vol_read} macros={this.props.macros} label={this.props.vol_read_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.cur_read} macros={this.props.macros} label={this.props.cur_read_label} alarmSensitive={true}/></Grid>
          <Grid item><ToggleButton pv={this.props.button} macros={this.props.macros}/></Grid>
        </Grid>
        </fieldset>
      </>
      )
  }
}

export default PowerSupply;
