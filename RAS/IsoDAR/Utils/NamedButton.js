import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';


import TextInput from '../../BaseComponents/TextInput';
import TextOutput from '../../BaseComponents/TextOutput';
import ToggleButton from '../../BaseComponents/ToggleButton';

class NamedButton extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <Grid item container direction="row"  justify="flex-start"  alignItems="center" style={{"width": "100%"}}>
          <Grid item style={{"width":"100%"}}><fieldset style={{"border":"0"}}><legend style={{"padding":"3px 6px", "text-align":"center"}}>{this.props.legend}</legend><ToggleButton pv={this.props.button} macros={this.props.macros}/></fieldset></Grid>
        </Grid>
      </>
      )
  }
}

export default NamedButton;