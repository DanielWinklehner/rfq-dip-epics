import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@material-ui/core/Grid';


import StyledIconIndicator from '../../BaseComponents/StyledIconIndicator';

class Indicator extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
        <StyledIconIndicator pv={this.props.pv} macros={this.props.macros} label={this.props.label} onColor={this.props.onColor} offColor={this.props.offColor}/>
      </>
      )
  }
}

export default Indicator;