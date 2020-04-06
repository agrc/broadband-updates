'''
This script automates the broadband feature class update process. 
update_features() deletes the old features from the master feature class (current_data_fc)
    and copies them from the updated feature class (new_data_fc) to the master.
    THE UPDATED FEATURE CLASS MUST HAVE ALL THE DATA (EXISTING + NEW) FOR THAT PROVIDER
It will optionally archive the existing data in the master feature class to an
    archive feature class (archive_fc)

Generally, you will call update_features() twice- once with archive enabled to copy
    the new data into the UBBMap BB_Service feature class while archiving the existing
    data to BB_Service_Archive, and then again w/o archiving to copy the new data 
    to SGID.UTILITIES.BroadbandService feature class.
'''

#: Manually create new feature class
#: Archive existing data for provider in BB feature class into archive feature class
#: Delete existing data from BB feature class
#: Copy data from new feature class into BB feature class
#: Delete existing data from SGID feature class
#: Copy data from new feature class into SGID feature class

import arcpy


def speedcode(down):
    '''
    Calculates the Utah Speed Code based on the max advertised download rate in Mb/s
    '''
    down = float(down)
    if down <= .2:
        code = '1'
    elif down > .2 and down < .768:
        code = '2'
    elif down >= .768 and down < 1.5:
        code = '3'    
    elif down >= 1.5 and down < 3:
        code = '4'
    elif down >= 3 and down < 6:
        code = '5'
    elif down >= 6 and down < 10:
        code = '6'
    elif down >= 10 and down < 25:
        code = '7'
    elif down >= 25 and down < 50:
        code = '8'
    elif down >= 50 and down < 100:
        code = '9'
    elif down >= 100 and down < 1000:
        code = '10'
    elif down >= 1000:
        code = '11'
    else:
        code = None

    return code


def archive_provider(provider, provider_field, current_data_fc, archive_fc, data_round):
    '''
    Add data_round and max download tier (MAXADDNTIA) to provider's current data and copy to archive_fc
    '''

    where = f'"{provider_field}" = \'{provider}\''
    current_data_fields = ['SHAPE@', 'UTProvCode', 'TransTech', 'MAXADDOWN', 
                           'MAXADUP', 'LastEdit', 'LastVerified', 'Identifier']
    archive_fields = ['SHAPE@', 'UTProvCode', 'TransTech', 'MAXADDOWN', 
                      'MAXADUP', 'LastEdit', 'LastVerified', 'Identifier', 
                      'DataRound', 'MAXADDNTIA']

    with arcpy.da.SearchCursor(current_data_fc, current_data_fields, where) as current_data_cursor, arcpy.da.UpdateCursor(archive_fc, archive_fields) as archive_cursor:
        
        for current_row in current_data_cursor:
            #: Build a row from the current data
            transfer_row = current_row[:]

            #: Calculate DataRound and MAXADDNTIA
            transfer_row.append(data_round)
            maxaddown = current_row[3]
            transfer_row.append(speedcode(maxaddown))

            #: insert row into archive data via Update Cursor
            archive_cursor.insertRow(transfer_row)
    


def update_features(provider_field, new_data_fc, current_data_fc, archive_fc="NA", data_round="NA", archive=True):
    '''
    Replaces a broadband provider's data in a master feature class (current_data_fc) with data
    from an update feature class (current_data_fc), optionally archiving the existing data 
    to an archive feature class (archive_fc).

    new_data_fc:         The new data to load into the master feature class. Must contain
                    all the features for that provider; if they only send new areas,
                    be sure to manually copy the existing areas into new_data_fc before 
                    updating. The provider name will be obtained from the 'UTProvCode'
                    field of this feature class; it must match the existing provider
                    name.
    current_data_fc: The provider's existing data in this feature class will be deleted 
                    and the contents of new_data_fc will be written in its place.
    archive_fc:     The provider's existing data will be copied from current_data_fc to this
                    feature class (if archive=True), using data_round to specify when
                    this happened.
    data_round      A text string to designate the current round of updates (for example,
                    for the spring 2019 update this was 'Spring 2019 - May 30 2019').
                    Thus, this field indicates when data was moved into the archive,
                    NOT when it was previously updated. If AllWest sends updates in 
                    Spring 2019, the existing data gets copied to the archive_fc with
                    a data_round of 'Spring 2019'.
    '''
    print('\n###')
    print(f'Updating {current_data_fc}')
    print('###')

    #: Make sure all our feature classes exist (prevents typos messing things up)
    if not arcpy.Exists(new_data_fc):
        raise ValueError(f'New feature class {new_data_fc} does not exist (typo?)')
    if not arcpy.Exists(current_data_fc):
        raise ValueError(f'Live feature class {current_data_fc} does not exist (typo?)')
    if archive and not arcpy.Exists(archive_fc):
        raise ValueError(f'Archive feature class {archive_fc} does not exist (typo?)')

    #: Get the new provider name from the new feature class
    with arcpy.da.SearchCursor(new_data_fc, provider_field) as name_cursor:
        provider = next(name_cursor)[0]

    #: Make sure new provider is valid
    print('\nChecking if provider is valid...')
    providers = []
    with arcpy.da.SearchCursor(current_data_fc, provider_field) as scursor:
        for row in scursor:
            if row[0] not in providers:
                providers.append(row[0])

    if provider not in providers:
        raise ValueError(f'{provider} not found in list of existing providers in {current_data_fc}.')

    #: Archive provider's current features
    #: Apparently, MAXADDNTIA only exists in the archive, not the UBB sde or the SGID.
    #: Make layer of only that provider's features from current live feature class
    print(f'\nMaking layer of {provider}\'s current features from {current_data_fc}...')
    live_layer_name = 'live'
    where_clause = f'"{provider_field}" = \'{provider}\''
    live_layer = arcpy.MakeFeatureLayer_management(current_data_fc, live_layer_name, where_clause)

    #: Get number of existing features
    existing_count = arcpy.GetCount_management(live_layer)
    print(f'({existing_count} existing features in layer)')
    
    if archive:
        print(f'\nAppending {provider}\'s current features to archive feature class {archive_fc}...')
        archive_provider(provider, provider_field, current_data_fc, archive_fc, data_round)

    #: Delete provider's features from live fc
    print(f'\nDeleting {provider}\'s current features from master feature class {current_data_fc}...')
    # arcpy.DeleteFeatures_management(live_layer)
    where = f'"{provider_field}" = \'{provider}\''
    with arcpy.da.UpdateCursor(current_data_fc, where) as current_data_cursor:
        for row in current_data_cursor:
            current_data_cursor.deleteRow()

    #: Append new features from local fc to live fc
    print(f'\nAppending new features from {new_data_fc} to master feature class {current_data_fc}...')
    arcpy.Append_management(new_data_fc, current_data_fc, 'TEST')
    print('\n### Finished ###\n')

    #: Explicit clean up
    arcpy.Delete_management('in_memory')

    #: NOTE
    #: For some reason, this fails with an error 464, can't get schema lock. However, if we
    #: don't delete it, subsequent calls to update_features (ie, updating the ubb fc and then 
    #: trying to update the SGID fc) fail because the layer already exists. Not sure yet how
    #: to fix this, need to bang against it more in the next update. 
    if live_layer:
        arcpy.Delete_management(live_layer)


def main():
    # provider_name = 'South Central'
    # ubb_fc = r'c:\gis\Projects\Broadband\scratch\script_test.gdb\BB_Service'
    # ubb_archive_fc = r'c:\gis\Projects\Broadband\scratch\script_test.gdb\BB_Service_Archive'
    # cleaned_updates_fc = r'c:\gis\Projects\Broadband\Spring 2019\South Central\SouthCentralCleaned.gdb\SC_Merged_Final'
    # data_round = 'Test'

    # provider_name = 'UTOPIA'
    ubb_fc = r'c:\gis\Projects\Broadband\ubbmap.agrc.utah.gov.sde\UBBMAP.UBBADMIN.BB_Service'
    sgid_fc = r'c:\gis\Projects\Broadband\UTILITIES_sgid.sde\SGID10.UTILITIES.BroadbandService'
    ubb_archive_fc = r'c:\gis\Projects\Broadband\ubbmap.agrc.utah.gov.sde\UBBMAP.UBBADMIN.BB_Service_Archive'
    data_round = 'Fall 2019 - October 17, 2019'

    # SC_fc = r'c:\gis\Projects\Broadband\Spring 2019\South Central\SouthCentralCleaned.gdb\SC_Merged_Final'
    # Utopia_fc = r'c:\gis\Projects\Broadband\Fall 2019\Utopia Coverage\UtopiaFall2019.gdb\Utopia_fall2019_template'
    # directcom = r'c:\gis\Projects\Broadband\Spring 2019\DirectCom\DirectcomCleaned.gdb\Directcom_cleaned'
    # tds = r'c:\gis\Projects\Broadband\Fall 2019\TDS\TDS.gdb\TDS_Template'
    # centurylink = r'c:\gis\Projects\Broadband\Fall 2019\CenturyLink\CenturyLink.gdb\CenturyLink_Fall19_Template'
    frontier = r'c:\gis\Projects\Broadband\Fall 2019\Frontier\Frontier.gdb\Frontier_Fall19_Template'

    #: Update UBB feature class
    # update_features(frontier, ubb_fc, ubb_archive_fc, data_round, archive=True)
    #: Update SGID feature class
    update_features('UTProvCode', frontier, sgid_fc, archive=False)


if __name__ == '__main__':
    main()