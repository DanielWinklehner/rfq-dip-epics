import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@mui/styles';
import { withRouter } from 'react-router-dom';

import Grid from '@mui/material/Grid';
import GraphY from '../BaseComponents/GraphY';
import TimeStampGraph from './Utils/TimeStampGraph.js'
import ModGraphY from './Utils/ModGraphY.js'

class Plots extends React.Component {

  render() {
    const { classes } = this.props;

    return (
      <>
      <Grid container sm={12} xs={12} style={{marginTop: '1vh', marginRight: "5vw", "justify-content":"space-between"}}>
        {/* <Grid item><TimeStampGraph legends={['Some Data']} pvs={['testIOC:test4']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid> */}
        {/* <Grid item><ModGraphY legends = {['Graph 1']} pvs={['testIOC:test4']} yUnits='torr' height='45vh' width='19vw' useTimeStamp={false} usePolling={true} pollingRate={100} /></Grid> */}
        {/* <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid>
        <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid> */}
      </Grid>
      <Grid container sm={12} xs={12} style={{marginTop: '1vh', marginRight: "5vw", "justify-content":"space-between"}}>
        <Grid item><TimeStampGraph legends = {['Source']} pvs={['pva://AU-20P7-1:voltage:read']} yUnits='V' width="19vw" height="45vh" usePolling={true} pollingRate={100}/></Grid>
        <Grid item><TimeStampGraph legends = {['Puller']} pvs={['pva://AU-20P7-2:voltage:read']} yUnits='V' width="19vw" height="45vh" usePolling={true} pollingRate={100}/></Grid>
        <Grid item><TimeStampGraph legends = {['Lens 1']} pvs={['pva://AU-20P7-3:voltage:read']} yUnits='V' width="19vw" height="45vh" usePolling={true} pollingRate={100}/></Grid>
        <Grid item><TimeStampGraph legends = {['Lens 3']} pvs={['pva://AU-20P7-4:voltage:read']} yUnits='V' width="19vw" height="45vh" usePolling={true} pollingRate={100}/></Grid>
        {/* <Grid item><TimeStampGraph legends={['Some Data']} pvs={['pva://testIOC:amplitude']} yUnits='A' height='45vh' width='19vw'></TimeStampGraph></Grid> */}
      </Grid>
      </>
    )
  }
}

Plots.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withRouter(Plots);
