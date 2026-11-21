/* eslint-disable eqeqeq */
/* eslint-disable no-unused-vars */
import React from 'react'
import AutomationStudioContext from '../../SystemComponents/AutomationStudioContext';
import withStyles from '@mui/styles/withStyles';
import PropTypes from 'prop-types';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Paper from '@mui/material/Paper';
import Popover from '@mui/material/Popover';
import MenuItem from '@mui/material/MenuItem';
import MenuList from '@mui/material/MenuList';
import Divider from '@mui/material/Divider';
import {Link} from 'react-router-dom'
import ListItemIcon from '@mui/material/ListItemIcon';
import ViewList from '@mui/icons-material/ViewList';
import Typography from '@mui/material/Typography';
import Lock from '@mui/icons-material/Lock';
import { Coffee,LanConnect,LanDisconnect,ContentCopy } from 'mdi-material-ui/'
import Modal from "@material-ui/core/Modal";
import TextField from '@mui/material/TextField';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';

class TestPopUp extends React.Component {
    constructor(props) {
        super(props);
        this.state={
          openContextMenu: false,
          menuSelectedIndex:0,
        }
    }

    render () {

    }
}