import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';


import TextInput from '../../BaseComponents/TextInput';
import TextOutput from '../../BaseComponents/TextOutput';
import ToggleButton from '../../BaseComponents/ToggleButton';

class IonGaugeController extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <fieldset>
        <legend style={{"padding":"3px 6px"}}>{this.props.legend}</legend>
        <Grid container spacing={1}  direction="row"  justify="flex-start"  alignItems="center" style={{display: "inline-flex", "flex-wrap":"nowrap"}}>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.apg} macros={this.props.macros} label={this.props.apg_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.diag_box} macros={this.props.macros} label={this.props.diag_box_label} alarmSensitive={true}/></Grid>
           
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.naim} macros={this.props.macros} label={this.props.naim_label} alarmSensitive={true}/></Grid>
          <Grid item style={{"position":"relative", "bottom":"10px"}}><fieldset><legend style={{"padding":"3px 6px", "text-align":"center"}}>{'Strike'}</legend><ToggleButton pv={this.props.button} macros={this.props.macros}/></fieldset></Grid>
        </Grid>
        </fieldset>
      </>
      )
  }
}

export default IonGaugeController;