import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import GraphY from '../../BaseComponents/GraphY';
import Grid from '@material-ui/core/Grid';


class TimeStampGraph extends React.Component {
  constructor(props) {
    super(props);
  }
  render() {
    return (
        <div style={{ height: this.props.height, width: this.props.width}}>
          <GraphY 
            pvs={this.props.pvs}
            maxLength={600}
            legend={this.props.legends}
            yUnits={this.props.yUnits}
            useTimeStamp={true}
            usePolling={true}
            pollingRate={60}
          />
        </div>
    )
  }
}

TimeStampGraph.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default TimeStampGraph;
