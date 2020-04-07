# broadband-updates

Scripts to make the manual broadband provider data update process easier.

## Installation

- Clone the repo to your local machine.
- Navigate to the included toolbox in ArcGIS Pro's catalog.

## update_provider.py

This is a script tool (in the accompanying toolbox) to assist in the update process for each broadband provider. After creating a new feature class containing all of the provider's service areas for the next update (all the new/changed areas as well as any unchanged areas), run this tool to load the data. It automatically performs the following tasks:

- Calculates the uuid/identifier (adding the Identifier field to the new feature class if needed).
- Archives the provider's existing features from a current feature class to an archive feature class, filling in the data round and max download tier information for each feature.
- Copies the new features into the current feature class, deleting all the provider's old features from the current feature class in the process. This step is done twice- once to load into the UBB database and again to load into the SGID.
