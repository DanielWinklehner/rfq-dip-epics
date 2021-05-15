import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';

import Grid from '@material-ui/core/Grid';

import TimeStampGraph from './Utils/TimeStampGraph.js'

class Plots extends React.Component {

  render() {
    return (
      <>
      <Grid container sm={12} xs={12} style={{marginTop: '8vh', marginRight: "0", "justify-content":"space-between"}}>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
      </Grid>
      <Grid container sm={12} xs={12} style={{marginRight: "0", "justify-content":"space-between"}}>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
      </Grid>
      </>
    )
  }

}

Plots.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default Plots;