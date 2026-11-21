import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@mui/material/Grid';


import TextInput from '../../BaseComponents/TextInput';
import TextOutput from '../../BaseComponents/TextOutput';
import ToggleButton from '../../BaseComponents/ToggleButton';

class FaradayCup extends React.Component {
  state = {
    have_button: 1,
  };
  constructor(props) {
    super(props);
    // this.state.have_button = 1;
    if (this.props.no_button === 1) {
      this.state.have_button = 0;
    }
  }
  render(){
      const have_button = this.state.have_button;
      return(
      <>
        <fieldset>
        <legend style={{"padding":"3px 6px"}}>{this.props.legend}</legend>
        <Grid container spacing={1}  direction="row"  justify="flex-start"  alignItems="center" style={{display: "inline-flex", "flex-wrap":"nowrap"}}>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.current} macros={this.props.macros} label={this.props.current_label} alarmSensitive={true}/></Grid>
          <Grid item><TextOutput prec={this.props.prec} pv={this.props.front_plate_current} macros={this.props.macros} label={this.props.front_plate_current_label} alarmSensitive={true}/></Grid>
          {have_button === 1 && <Grid item><ToggleButton pv={this.props.button} macros={this.props.macros} button_text={['Out', 'In']}/></Grid>}
        </Grid>
        </fieldset>
      </>
      )
  }
}

export default FaradayCup;
