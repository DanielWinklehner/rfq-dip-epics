import React from 'react';
import PropTypes from 'prop-types';
import Grid from '@mui/material/Grid';
import BeamLineCanvas from '../../SvgBeamlineComponents/BeamLineCanvas';
import HorizontalBeamline from '../../SvgBeamlineComponents/HorizontalBeamline';
import EmiVert from './Svgs/EmiVert';
import Test from './Svgs/test';
import QuadrapoleMagnet from '../../SvgBeamlineComponents/QuadrapoleMagnet';
import BendingMagnet from '../../SvgBeamlineComponents/BendingMagnet';
import SteererYMagnet from '../../SvgBeamlineComponents/SteererYMagnet';
import SteererXMagnet from '../../SvgBeamlineComponents/SteererXMagnet';
import SteererXYMagnet from '../../SvgBeamlineComponents/SteererXYMagnet';

class Beamline extends React.Component {
  constructor(props) {
    super(props);
  }
  render(){
      return(
      <>
      <BeamLineCanvas width={400} height={200} >
        <HorizontalBeamline 
          x={0}
          y={-50}
          pv={'pva://testIOC:BeamlineA:BeamOn'}
          width={'113px'}
        />

        <Test
          x={0}
          y={-50}
          label= 'EMI'
              pv= '$(IOC):$(device):Readback'
              macros=
                {{
                '$(IOC)': 'pva://testIOC',
                '$(device)': 'PS4',
                }}
          usePvUnits={true}
          usePvLabel={false}
          alarmSensitive={true}
          label='EMI'
          componentShadow={true}
          textShadow={false}
          componentGradient={true}
          valueOffsetY={15}
        />

        <HorizontalBeamline 
          x={'133px'}
          y={-50}
          pv={'pva://testIOC:BeamlineB:BeamOn'}
          width={'148px'}
        />
        {/* <EmiVert
          pv='pva://$(IOC):$(actuatorName)$(sim):put-outIn'
          isMovingPv='pva://$(IOC):$(actuatorName)$(sim):get-status.B5'
          inLimitPv='pva://$(IOC):$(actuatorName)$(sim):get-status.B6'
          outLimitPv='pva://$(IOC):$(actuatorName)$(sim):get-status.B7'
          inLimitValue={1}
          outLimitValue={1}
          isMovingValue={1}

          label='$(actuatorName)'
          macros={{
            '$(IOC)': 'testIOC',
            '$(sim)': 'sim',
            '$(actuatorName)': 'EmiVert',
          }}
          x={220}
          y={-50}
          alarmSensitive={true}
          componentGradient={true}

        /> */}
        <HorizontalBeamline 
          x={'261px'}
          y={-50}
          pv={'pva://testIOC:BeamlineC:BeamOn'}
          width={'10px'}
        />
        
        {/* <QuadrapoleMagnet
          //handleOnClick={handleOnSystemClick}
          x={0}
          y={-50}
          label='Q3'
              pv= '$(IOC):$(device):Readback'
              macros=
              {{
                '$(IOC)': 'pva://testIOC',
                '$(device)': 'PS3',
                }}
            usePvUnits={true}
          usePvLabel={false}
          alarmSensitive={true}
          
          componentShadow={true}
          textShadow={false}
          componentGradient={true}
        /> */}
        <BendingMagnet
          x={75}
          y={-50}
          label= 'BM1'
              pv= '$(IOC):$(device):Readback'
              macros=
                {{
                '$(IOC)': 'pva://testIOC',
                '$(device)': 'PS4',
                }}
          usePvUnits={true}
          usePvLabel={false}
          alarmSensitive={true}
          label='BM1'
          componentShadow={true}
          textShadow={false}
          componentGradient={true}
          valueOffsetY={15}
        />
        <SteererXYMagnet
              
                
                xPv={'$(IOC):$(device):X:Readback'}
                yPv={'$(IOC):$(device):Y:Readback'}  
                label='STRXY2'
                macros= {{
                    '$(IOC)': 'pva://testIOC',
                    '$(device)': 'STR2',
                    
                }
                }
                x={165}
                y={-50}
                usePvUnits={true}
                prec={3}
            valueOffsetY={15}
            labelOffsetY={-15}
                alarmSensitive={true}
                
              />
        <SteererYMagnet
          pv={'$(IOC):$(device):$(XorY):Readback'}
              label='STR2'
              macros= {{
                    '$(IOC)': 'pva://testIOC',
                    '$(device)': 'STR2',
                    '$(XorY)': 'Y'
                }
              }
          x={150}
          y={-50}
          usePvUnits={true}
          prec={3}
          alarmSensitive={true}
          labelOffsety={-50}
          labelOffsetX={0}
          valueOffsety={-50}
          valueOffsetX={0}
          componentShadow={true}
          textShadow={false}
          componentGradient={true}
        />
        
      </BeamLineCanvas>
      </>
      )
  }
}

export default Beamline;
