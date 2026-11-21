import React, { useState } from 'react'
import Button from '@mui/material/Button';
import Widget from '../../../SystemComponents/Widgets/Widget';
import { withStyles } from '@mui/styles';
import { svgHeight, svgCenterY, svgWidth, svgCenterX } from '../../../SystemComponents/svgConstants.js';
import { v4 as uuidv4 } from 'uuid';
import PropTypes from 'prop-types';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Slide from '@mui/material/Slide';



const Transition = React.forwardRef(function Transition(props, ref) {
  return <Slide direction="up" ref={ref} {...props} />;
});

const styles = theme => ({


  Label: {
    fill: theme.palette.text.primary

  },
  Value: {
    fill: theme.palette.text.primary

  },

});
/* eslint-disable eqeqeq */
/* eslint-disable no-unused-vars */
const EmiVertComponent = (props) => {

  const [dialogOpen, setDialogOpen] = useState(false);

  const handleYes = () => {
    let newValue = props.value == 1 ? 0 : 1;
    props.handleImmediateChange(newValue);
    setDialogOpen(false);

  };

  const handleOnClick = () => {

    let newValue = props.value == 1 ? 0 : 1;

    props.handleImmediateChange(newValue)
  };
  // const handleContextMenu = event => {
  //   props.handleToggleContextMenu(event);

  // };
  let yOffset = 0;
  const { classes } = props;
  const { initialized } = props;

  const { alarmSeverity } = props;
  const { value } = props;
  const { pvsData } = props;
  let isIn = true;
  let isOut = false;
  let isMoving = false;
  let inLimitPvIndex;
  let inLimitPv;
  if (props.inLimitPv) {
    inLimitPvIndex = 0;
    inLimitPv = pvsData[inLimitPvIndex];
  }
  else {
    inLimitPvIndex = -1;
  }
  let outLimitPvIndex;
  let outLimitPv;
  if (props.inLimitPv) {
    outLimitPvIndex = 1;
    outLimitPv = pvsData[inLimitPvIndex + outLimitPvIndex];
  }
  else {
    outLimitPvIndex = -1;
  }
  let isMovingPvIndex;
  let isMovingPv;
  if (props.inLimitPv) {
    isMovingPvIndex = 2;
    isMovingPv = pvsData[inLimitPvIndex + outLimitPvIndex + outLimitPvIndex];
  }
  else {
    outLimitPvIndex = -1;
  }
  if (initialized) {
    let inValue = props.inLimitPv ? inLimitPv.value : value;
    let inLimitValue = props.inLimitValue ? props.inLimitValue : 1;

    isIn = inValue == inLimitValue;
    //  console.log(inValue,inLimitValue,isIn,inLimitPv)
    let outValue = props.outLimitPv ? outLimitPv.value : value;
    let outLimitValue = props.outLimitValue ? props.outLimitValue : 1;
    isOut = outValue == outLimitValue;
    //isIn = value=='0';

    let isMovingValue = props.isMovingPv ? isMovingPv.value : value;
    let isMovingValueValid = props.isMovingValue ? props.isMovingValue : 1;


    isMoving = props.isMovingValue ? isMovingValue == isMovingValueValid : (!(isIn || isOut));
    yOffset = isIn ? 0 : -35;

  }
  else {
    yOffset = 0;
  }
  let color = '';
  if (initialized) {
    if (props.alarmSensitive !== 'undefined') {
      if (props.alarmSensitive == true) {
        if (alarmSeverity == 1) {
          color = props.theme.palette.alarm.minor.main;

        }
        else if (alarmSeverity == 2) {
          color = props.theme.palette.alarm.major.main;

        }
        else {
          if (isMoving) {
            color = '#f9e500';
          }
          else {
            color = props.theme.palette.beamLineComponent.main;
          }

        }


      }

    }

  }
  else {
    color = 'grey';
  }

  const componentId = uuidv4();
  //console.log(isIn)

  return (



    <svg
      x={props.x}
      y={props.y}

      width={svgWidth}
      height={svgHeight}
    >

      <g
        transform={'translate(' + svgCenterX + ',' + (svgCenterY - 2.5) + ')'}

      //    onContextMenu={handleContextMenu}
      >


        <g>


          <Dialog
            open={dialogOpen}
            TransitionComponent={Transition}
            keepMounted
            onClose={() => setDialogOpen(false)}
            aria-labelledby="alert-dialog-slide-title"
            aria-describedby="alert-dialog-slide-description"
          >
            <DialogTitle id="alert-dialog-slide-title">
              {"Warning!"}
            </DialogTitle>
            <DialogContent>
              <DialogContentText id="alert-dialog-slide-description">
                Are you sure you want to remove the Emittance Vert?
                  </DialogContentText>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDialogOpen(false)} color="primary">
                No
                  </Button>
              <Button onClick={handleYes} color="primary">
                Yes
                  </Button>
            </DialogActions>
          </Dialog>



          <linearGradient id={componentId + 'EmiVert-gradient'} gradientTransform="rotate(0)">
          <stop offset="0%" stopColor={'silver'} />
                        <stop offset="65%" stopColor={color} />
          </linearGradient>
          <defs>
            <filter id={componentId + "EmiVertShadow"} x="0" y="0" width="600%" height="500%">
              <feOffset result="offOut" in="SourceGraphic" dx="2" dy="2" />
              <feColorMatrix result="matrixOut" in="offOut" type="matrix"
                values="0.2 0 0 0 0 0 0.2 0 0 0 0 0 0.2 0 0 0 0 0 1 0" />
              <feGaussianBlur result="blurOut" in="matrixOut" stdDeviation="1" />
              <feBlend in="SourceGraphic" in2="blurOut" mode="normal" />
            </filter>
          </defs>

          <g
            fill={props.componentGradient === true ? 'url(#' + componentId + 'EmiVert-gradient)' : color}
            filter={props.componentShadow === true ? "url(#" + componentId + "EmiVertShadow)" : ""}
            onClick={isIn ? () => setDialogOpen(true) : handleOnClick}
          >
            {yOffset !== 0  && <g transform={'translate(-11,-1140)'}>
              <path
                d="m 3.2879796,1122.4204 c -1.2852323,-0.084 -1.5029316,-0.1209 -1.1719195,-0.2014 0.1791184,-0.043 0.5666595,-0.2704 0.7975976,-0.4662 1.6785753,-1.4252 3.0788061,-5.7048 3.6656823,-11.2038 0.195042,-1.8277 0.2763907,-3.29 0.297677,-5.351 0.036502,-3.535 -0.1932037,-6.6349 -0.7107832,-9.5922 -0.3826264,-2.1864 -0.8317616,-3.8473 -1.4551449,-5.3815 -0.7283328,-1.7928 -1.587264,-2.9311 -2.4746797,-3.2803 -0.1952031,-0.078 -0.2017864,-0.084 -0.1106923,-0.1093 0.1205222,-0.035 1.2221931,-0.1066 2.1584862,-0.1411 1.1404741,-0.043 2.8140282,0.053 4.2616262,0.2503 5.8683487,0.7943 11.1733747,3.604 14.5144387,7.6873 0.570693,0.6973 0.880617,1.1339 1.370907,1.931 1.558755,2.5337 2.323424,5.1761 2.323424,8.0286 0,2.2956 -0.525865,4.5248 -1.575169,6.6774 -0.209551,0.4298 -0.747136,1.3504 -1.095266,1.8757 -2.376667,3.5854 -6.32174,6.4653 -10.9765,8.0124 -2.645862,0.8797 -5.4712766,1.3212 -8.3253487,1.3007 -0.5555337,0 -1.2279842,-0.029 -1.4943364,-0.037 z"
              />
              <ellipse
                cx="1.4687502"
                cy="1104.5706"
                rx="5.3938155"
                ry="17.737566" />




            </g>
            }

            {yOffset === 0  &&     <g
       id="g8495">
      <path
      
         id="path8478"
         d="M 24.149959,1064.5524 5.135178,1049.0529 h 10.000004 l 19.014781,15.4995 z"
         style={{"fill":"none", "stroke":"#000000", "stroke-width":0.1, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}}
          />
      <path
      
         id="path8480"
         d="m 0.04018281,1106.8979 1.41294219,-16.1439 10.578125,-0.016 1.208307,1.0171 0.837821,-9.512 -3.126797,-2.5487 -0.106831,1.0124 h -8.5625 l 2.853928,-31.6543 19.014781,15.4995 -5.094995,57.845 z"
         style={{"fill":"none", "stroke":"#000000", "stroke-width":0.1, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}} 
         />
      <path
      
         id="path8484"
         d="m 12.03125,1090.738 1.34375,0.032 -0.135443,0.9854 -1.208307,-1.0171"
         style={{"fill":"none", "stroke":"#000000", "stroke-width":0.1, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}}
          />
      <path
      
         id="path8486"
         d="m 10.950581,1079.6944 1.268169,0.9815 -1.375,0.031 z"
         style={{"fill":"none", "stroke":"#000000", "stroke-width":0.1, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}}
          />
      <path
      
         id="path8488"
         d="m 24.149959,1064.5524 h 10.000004 l -5.094995,57.845 -10.000004,-4e-4 z"
         style={{"fill":"none", "stroke":"#000000", "stroke-width":0.1, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}}
          />
      <path
      style={{"fill":"none", "stroke":"#000000", "stroke-width":0.113386, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}}
         d="m 30.178398,1109.7486 2.774958,-31.4476 38.850044,0.073 -2.68382,31.4634 z"
         id="path871"
         />
      <path
      style={{"fill":"none", "stroke":"#000000", "stroke-width":0.113386, "stroke-linecap":"butt", "stroke-linejoin":"miter", "stroke-miterlimit":4, "stroke-dasharray":"none", "stroke-opacity":1}}
      d="m 71.8034,1078.374 -10.72705,-8.8419 -27.356194,0.088 -0.7668,8.6806 z"
         id="path875" 
         />
    </g>




            }
          </g>
          <text className={classes.Label}
            x={0}
            y={+yOffset - 30}
            textAnchor='middle'
            filter={props.textShadow === true ? "url(#" + componentId + "FCShadow)" : ""}
          >
            {props.label}
          </text>
        </g>
      </g>





    </svg>
  );
}




/**
* EmiVert Beam line component
*
*  The label, min, max, units, pv and tooltip all accept macros that can be replaced by the values defined in the macros prop.
*/

const EmiVert = (props) => {

  let pvs=[];
  if( typeof props.isMovingPv!=='undefined'){
    pvs=[props.inLimitPv, props.outLimitPv, props.isMovingPv]
  }
  else{
    pvs=[props.inLimitPv, props.outLimitPv]
  }
  return (
    <Widget svgWidget={true}  {...props} component={EmiVertComponent}
      pvs={pvs}
      label={props.label} />

  )
}
EmiVert.propTypes = {


  /**
  * Directive to use the  alarm severity status to alter the fields background color.
  */

  alarmSensitive: PropTypes.bool,
  /**
   * Custom PV to define the alarm severity to be used, alarmSensitive must be set to `true` and useMetadata to `false`, NB must contain correct prefix ie: pva:// eg. 'pva://$(device):test$(id)'.
   */
  alarmPv: PropTypes.string,
  /**
   * If defined, then the DataConnection and
   * the widget debugging information will be displayed.
   */
  debug: PropTypes.bool,

  /**
   * Local variable initialization value.
   * When using loc:// type PVs.
   */
  initialLocalVariableValue: PropTypes.string,
  /**
   * Custom label to be used, if  usePvLabel is not defined.
   */
  label: PropTypes.string,
  /**
  * Custom PV to define the units to be used, usePvLabel must be set to `true` and useMetadata to `false`, NB must contain correct prefix ie: pva:// eg. 'pva://$(device):test$(id)'.
  */
  labelPv: PropTypes.string,
  /**
   * Values of macros that will be substituted in the pv name.
   * eg. {{'$(device)':'testIOC','$(id)':'2'}}
   */
  macros: PropTypes.object,

  /**
   * Directive to prevent more FCs being inserted if the maximum is reached.
   */
  maxFCsReached: PropTypes.bool,





  /**
   * Directive to fill the component's label with
   * the value contained in the  pv metadata's DESC field or the labelPv value.
   * If not defined it uses the custom label as defined by the label prop.
   */
  usePvLabel: PropTypes.bool,
  /**
   * When using EPICS, the RAS pv's metadata is conventionally derived from the pyEpics PV in the pvserver.
   * The pyEpics metadata is unfortunately static and the values used will be the initial values that pvserver receives when it connects the first time.
   * This is sufficient in most cases except when the user wants to dynamically update the metaData.
   * In this case a direct connection can be made to all the pv fields by setting useMetadata to false.
   * If any of the metadata pvs are defined i.e unitsPv then the PV makes a new data  connection to this alternate pv and will
   * use the value provided by this pv as the units.
   * The same is the case for the precPV, labelPv, alarmPv, unitsPv and minPv.
   * By setting useMetadata to false also enables connection to other variables as defined by different protocols.
   */
  useMetadata: PropTypes.bool,

  /**
   * Directive to use PV's string values.
   */
  useStringValue: PropTypes.bool,






  /** Name of the pv process variable that sends the command 1 for out and 0 for in, NB must contain correct prefix ie: pva://  eg. 'pva://$(device):test$(id)'*/
  pv: PropTypes.string,
  /** Name of the `in` limit pv process variable, if not defined the pv value==0 is used , NB must contain correct prefix ie: pva://  eg. 'pva://$(device):test$(id)'*/
  inLimitPv: PropTypes.string,
  /** Value to override the default value inLimitPv value is compared too. Valid values: `1` or `0` */
  inLimitValue: PropTypes.number,
  /** Name of the `out` limit pv process variable, if not defined the pv value==1 is used , NB must contain correct prefix ie: pva://  eg. 'pva://$(device):test$(id)'*/
  outLimitPv: PropTypes.string,
  /** Value to override the default value outLimitPv value is compared too. Valid values: `1` or `0` */
  outLimitValue: PropTypes.number,
  /** Name of the `is Moving` pv process variable, if not defined it is not used , NB must contain correct prefix ie: pva://  eg. 'pva://$(device):test$(id)'*/
  isMovingPv: PropTypes.string,
  /** Value to override the default value isMovingPv value is compared too. Valid values: `1` or `0` */
  isMovingValue: PropTypes.number,
  /**
  * Tooltip Text
  */
  tooltip: PropTypes.string,
  /**
   * Directive to show the tooltip
   */
  showTooltip: PropTypes.bool,
  /**
   *  Any of the MUI Tooltip props can applied by defining them as an object
   */

  tooltipProps: PropTypes.object,
  /**
   *  A System description object the passed to the callback function when the item is clicked on
   */

  system: PropTypes.object,
  /**
   *  A callback function when the item is clicked on, returns the system object
   */

  handleOnClick: PropTypes.func,
  /**
   * Y Offset for the label
   */
  labelOffsetY: PropTypes.number,
  /**
   * X Offset for the label
   */
  labelOffsetX: PropTypes.number,
  /**
  * Y Offset for the pv value
  */
  valueOffsetY: PropTypes.number,
  /**
   * X Offset for the pv value
   */
  valueOffsetX: PropTypes.number,
  /**
   * enable a shadow behind the text
   */
  textShadow: PropTypes.bool,
  /**
   * use a gradient fil on the component
   */
  componentGradient: PropTypes.bool,
  /**
   * enable a shadow behind the component
   */
  componentShadow: PropTypes.bool,
  /**
   * Direct to show the label
   */
  showLabel: PropTypes.bool,
  /**
   * Direct to show the value
   */
  showValue: PropTypes.bool,



};
EmiVert.defaultProps = {
  debug: false,
  showLabel: true,
  showValue: true,
  alarmSensitive: false,
  showTooltip: false,
  labelOffsetY: 0,
  labelOffsetX: 0,
  valueOffsetY: 0,
  valueOffsetX: 0,
  componentShadow: true,
  textShadow: false,
  componentGradient: true,
};


export default withStyles(styles, { withTheme: true })(EmiVert)


