import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import Typography from '@material-ui/core/Typography';


import TraditionalLayout from '../UI/Layout/ComposedLayouts/TraditionalLayout.js';

import Home from "./Home.js"
import Plots from "./Plots.js"
import Vacuum from "./Vacuum.js"
import Safety from "./Safety.js"
import Beamline from "./BeamlinePage.js"

function TabContainer(props) {
  return (
    <Typography component="div" style={{ padding: 8 * 1, paddingTop: 36 }}>
      {props.children}
    </Typography>
  );
}

TabContainer.propTypes = {
  children: PropTypes.node.isRequired,
};

const styles = theme => ({
  root: {
    flexGrow: 1,
    width: '100%',
    backgroundColor: theme.palette.background.paper,
  },
  card: {
    padding: theme.spacing(2),
  }
});

class Main extends React.Component {
  state = {
    value: 0,
  };

  handleChange = (event, value) => {
    this.setState({ value });
  };

  render() {
    const { value } = this.state;
    return (
      <div>
        <TraditionalLayout
          title="IsoDAR Control System"
          denseAppBar
          alignTitle="center"
          tabs={['Ion Source', 'Plots', 'Vacuum', 'Safety', 'Beamline']}
          handleTabChange={this.handleChange}
          tabValue={value}
        />
        {value === 0 && <TabContainer><Home/></TabContainer>}
        {value === 1 && <Plots/>}
        {value === 2 && <Vacuum/>}
        {value === 3 && <TabContainer><Safety/></TabContainer>}
        {value === 4 && <Beamline/>}
      </div>
    )
  }

}

Main.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styles, { withTheme: true })(Main);