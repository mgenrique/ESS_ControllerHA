# ESS_ControllerHA
![ess_controller](_images/icon.png)

The **ESS controller** is a target soc calculator for **Home Assistant**. It is a custom component that uses data from different sources to perform hourly scheduling of the system's battery SoC, so that the cost of purchasing energy from the grid is minimal. To do this, it obtains historical data from **InfluxDB** about the home consumption, actual solar production and the historical predictions obtained from **Forecast.Solar**.
Using the **Prophet** library, it generates demand forecasts for the next few hours.
The electricity purchase and sale prices are obtained from the official **ESIOS** component (Spain electricity hourly price PVPC), so for the moment, the component is only useful for the Spanish territory.
The solar production forecasts are obtained from Forecast.Solar and will be weighted by hours with the success coefficients obtained from the analysis of historical data, before sending them to the target calculator.
The configuration flow asks the user for the parameters necessary to characterize the installation (battery data, location, and system power and efficiency).
The development has been done on a system with a **Victron Energy** Multiplus inverter but it is adaptable to any inverter model that is capable of providing information in the form of Home Assistant sensors.

With all the above information, the software coordinates all the information sources to pose a linear programming problem that is solved using **PuLP**.

The final result is a SoC schedule that the system must try to follow.

With this information, the Modbus connection with the inverter is used to maintain the grid set point that allows the calculated SoC to be reached.
