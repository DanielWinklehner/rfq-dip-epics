import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@mui/material/Grid';


import TextOutput from '../../BaseComponents/TextOutput';

class WaterFlowController extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <fieldset>
        <legend style={{"padding":"3px 6px"}}>{this.props.legend}</legend>
        <Grid container spacing={1}  direction="row"  justify="flex-start"  alignItems="center" style={{display: "inline-flex", "flex-wrap":"nowrap"}}>
          {/* <Grid item><TextOutput prec={this.props.prec} pv={this.props.read1} macros={this.props.macros} label={this.props.read1_label} alarmSensitive={true}/></Grid> */}
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.read2} macros={this.props.macros} label={this.props.read2_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.read3} macros={this.props.macros} label={this.props.read3_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.read4} macros={this.props.macros} label={this.props.read4_label} alarmSensitive={true}/></Grid>
          {/* <Grid item><TextOutput prec={this.props.prec} pv={this.props.read5} macros={this.props.macros} label={this.props.read5_label} alarmSensitive={true}/></Grid> */}
        </Grid>
        </fieldset>
      </>
      )
  }
}

export default WaterFlowController;
