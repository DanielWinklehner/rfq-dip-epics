# RAS 
First read instructions for setting up RAS from [here](https://github.com/DanielWinklehner/rfq-dip-epics/wiki). The folder `IsoDAR` in this repository should be added to the path `ReactApp/scr/components`.

Make sure to add IPs to `.env`. In addition, add following two lines to `ReactApp/scr/Routes.js` to access `/isodar`:
```js
import Main from './components/IsoDAR/Main'; // this should be added to the top of the file
<Route exact path="/isodar" component={Main}/> // this should be added inside <Switch> tag
```
In `IsoDAR`, you will find the components of pages and another folder `Utils` which contain the utility functions used in the page-components. In the next sections, we talk about them in some detail.

## Pages
We currently have 5 pages:
- Ion Source (Home.js): contains the elements of Ion Source controller. Also has two time-stamp graphs, for which PVs still need to be added.
- Plots (Plots.js): contains 10 plots in a responsive format to fit in the screen. All the current PVs for them are temporary.
- Vacuum (Vacuum.js): contains three plots, Ion-Gauge controller, and Valves.
- Safety (Safety.js): contains indicators for HV interlocks, Water-Flow controller (WFC), temperature sensors, Ion-Gauge controller (IGC), and two graphs, which should display the values for WFC and IGC. 
- Beamline (Beamline.js): contains the beamline (will be mentioned later), three graphs, and corresponding to each graph, three columns of elements. 

## Handling devices
All the devices should be found in and added to `Devices.js`. Each page-component imports the required devices from `Devices.js` and adds them to the state of the page . We use `jsx` looping render all the devices in a concise way. In case you need to use only some of the devices, you can manually add them to the state in `constructor(props)`.

## Utils
For each utility-component, we pass necessary properties from the super-component and use the components from `RAS` itself to render them. For example, in `FaradayCup.js`, we import `TextOutput` and `ToggleButton` of RAS to display read values and button elements. In each, we also push the properties via `this.props` (e.g. `this.props.button_pv`). The folder `Svgs` are mentioned in the next section.

## Beamline
RAS already has several components located in `ReactApp/src/SvgBeamlineComponents`. To learn more about them, you can use RAS Styleguide at `localhost:6060` (make sure to run style guide as well with docker). In the `Utils/Svgs` folder, we have added `test.js` to represent a Vertical Emittance Scanner (not tested). Using actual SVG files to create those components is hard to set up, so we recommend importing one of the existing svg file from `ReactApp/src/svg` to [InkScape](https://inkscape.org/) and add (advisedly simple) drawings.

The actual beamline is based on the component `BeamlineCanvas` of specified width and height. All other components that are supposed to be represented in beamline should be added inside that tag. Each of the components inside should take necessary elements (e.g. `pv`) along with their `x` and `y` coordinates relative to `BeamlineCanvas`. The beam of the beamline is rendered with `HorizontalBeamline` component. Refer to `Beamline.js` in `Utils` folder for more examples.
