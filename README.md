# BackBox Device OS Upgrade
##BackBox 7.0 Add Devices to an Upgrade Job

This project provides example code for how to use BackBox APIs to authenticate to BackBox, select Network and Security infrastructure devices based on IDs from a 3rd party system, select those devices in BackBox, place them in an upgrade job, add an upgrade file to BackBox, and add that file to the upgrade job. 

What you will need to get started
<li>Install of BackBox (https://www.backbox.com/request-a-demo/)</li>
<li>Add devices and set externail IDs that match the IDs in Devices_To_Upgrade.csv</li>
<li>A Task Job that utilizes the Cisco -> IOS -> SCP -> Upgrade automation in BackBox. To use the default values in the script you will need to name this job UpgradeJob </li>

The main set of code is BackBoxDeviceOSUpgrade.ipynb

upgradefile.tgz is a dummy file that is used to demontrate the ability to upload files to BackBox.

Devices_To_Upgrade.csv contains a single column of external device IDs that are used in our code to find the devices we intend to operate on.
