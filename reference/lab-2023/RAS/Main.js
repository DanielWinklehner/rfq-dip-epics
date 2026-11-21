import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@mui/styles';
import Typography from '@mui/material/Typography';


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
        {/* Making the tab containers like this will allow the objects to persist and not be deleted when changing tabs */}
        <div style={{ display: value === 0? 'block': 'none'}}>
          <TabContainer><Home/></TabContainer>
        </div>
        <div style={{ display: value === 1? 'block': 'none'}}>
          <TabContainer><Plots/></TabContainer>
        </div>
        <div style={{ display: value === 2? 'block': 'none'}}>
          <TabContainer><Vacuum/></TabContainer>
        </div>
        <div style={{ display: value === 3? 'block': 'none'}}>
          <TabContainer><Safety/></TabContainer>
        </div>
        <div style={{ display: value === 4? 'block': 'none'}}>
          <TabContainer><Beamline/></TabContainer>
        </div>
        {/* {value === 0 && <TabContainer><Home/></TabContainer>}
        {value === 1 && <TabContainer><Plots/></TabContainer>}
        {value === 2 && <TabContainer><Vacuum/></TabContainer>}
        {value === 3 && <TabContainer><Safety/></TabContainer>}
        {value === 4 && <TabContainer><Beamline/></TabContainer>} */}
      </div>
    )
  }
}

Main.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styles, { withTheme: true })(Main);
