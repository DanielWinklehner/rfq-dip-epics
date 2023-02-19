import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@mui/styles';
import GraphY from '../../BaseComponents/GraphY';
import ModGraphY from './ModGraphY';
import Grid from '@mui/material/Grid';
import { withRouter } from 'react-router-dom';

class TimeStampGraph extends React.Component {
  constructor(props) {
    super(props);
  }
  render() {
    return (
        <div style={{ height: this.props.height, width: this.props.width}}>
          <ModGraphY 
            pvs={this.props.pvs}
            maxLength={600}
            legend={this.props.legends}
            yUnits={this.props.yUnits}
            useTimeStamp={true}
            usePolling={false}
            pollingRate={100}
          />
        </div>
    )
  }
}

TimeStampGraph.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withRouter(TimeStampGraph);
