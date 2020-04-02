'''
This script automates the broadband feature class update process. 
update_features() deletes the old features from the master feature class (live_fc)
    and copies them from the updated feature class (new_fc) to the master.
    THE UPDATED FEATURE CLASS MUST HAVE ALL THE DATA (EXISTING + NEW) FOR THAT PROVIDER
It will optionally archive the existing data in the master feature class to an
    archive feature class (archive_fc)

Generally, you will call update_features() twice- once with archive enabled to copy
    the new data into the UBBMap BB_Service feature class while archiving the existing
    data to BB_Service_Archive, and then again w/o archiving to copy the new data 
    to SGID.UTILITIES.BroadbandService feature class.
'''

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


def update_features(new_fc, live_fc, archive_fc="NA", data_round="NA", archive=True):
    '''
    Replaces a broadband provider's data in a master feature class (live_fc) with data
    from an update feature class (live_fc), optionally archiving the existing data 
    to an archive feature class (archive_fc).

    new_fc:         The new data to load into the master feature class. Must contain
                    all the features for that provider; if they only send new areas,
                    be sure to manually copy the existing areas into new_fc before 
                    updating. The provider name will be obtained from the 'UTProvCode'
                    field of this feature class; it must match the existing provider
                    name.
    live_fc:        The provider's existing data in this feature class will be deleted 
                    and the contents of new_fc will be written in its place.
    archive_fc:     The provider's existing data will be copied from live_fc to this
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
    print(f'Updating {live_fc}')
    print('###')

    #: Make sure all our feature classes exist (prevents typos messing things up)
    if not arcpy.Exists(new_fc):
        raise ValueError(f'New feature class {new_fc} does not exist (typo?)')
    if not arcpy.Exists(live_fc):
        raise ValueError(f'Live feature class {live_fc} does not exist (typo?)')
    if archive and not arcpy.Exists(archive_fc):
        raise ValueError(f'Archive feature class {archive_fc} does not exist (typo?)')

    #: Get the provider name from the new feature class
    with arcpy.da.SearchCursor(new_fc, 'UTProvCode') as name_cursor:
        provider = next(name_cursor)[0]

    #: Make sure provider is valid
    print('\nChecking if provider is valid...')
    providers = []
    with arcpy.da.SearchCursor(live_fc, 'UTProvCode') as scursor:
        for row in scursor:
            if row[0] not in providers:
                providers.append(row[0])

    if provider not in providers:
        raise ValueError(f'{provider} not found in list of providers.')

    #: Archive provider's current features
    #: Make layer of only that provider's features from current live feature class
    print(f'\nMaking layer of {provider}\'s current features from {live_fc}...')
    live_layer_name = 'live'
    where_clause = f'"UTProvCode" = \'{provider}\''
    live_layer = arcpy.MakeFeatureLayer_management(live_fc, live_layer_name, where_clause)

    #: Get number of existing features
    existing_count = arcpy.GetCount_management(live_layer)
    print(f'({existing_count} existing features in layer)')
    
    if archive:
        #: Copy provider's features from the layer to in_memory feature class
        print(f'\nCopying {provider}\'s current features to temporary feature class...')
        live_copy_fc = r'in_memory\live'
        arcpy.CopyFeatures_management(live_layer, live_copy_fc)

        print('\nAdding fields and calculating...')
        #: Add archive fields and calculate values
        arcpy.AddField_management(live_copy_fc, 'DataRound', 'TEXT', field_length=50)
        arcpy.AddField_management(live_copy_fc, 'MAXADDNTIA', 'TEXT', field_length=2)

        with arcpy.da.UpdateCursor(live_copy_fc, ['DataRound', 'MAXADDOWN', 'MAXADDNTIA']) as ucursor:
            for row in ucursor:
                row[0] = data_round
                row[2] = speedcode(row[1])
                ucursor.updateRow(row)

        #: Append from updated in_memory feature class to archive
    
        print(f'\nAppending {provider}\'s current features to archive feature class {archive_fc}...')
        arcpy.Append_management(live_copy_fc, archive_fc, 'NO_TEST')


    #: Delete provider's features from live fc
    print(f'\nDeleting {provider}\'s current features from master feature class {live_fc}...')
    arcpy.DeleteFeatures_management(live_layer)

    #: Append new features from local fc to live fc
    print(f'\nAppending new features from {new_fc} to master feature class {live_fc}...')
    arcpy.Append_management(new_fc, live_fc, 'TEST')
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
    update_features(frontier, sgid_fc, archive=False)


if __name__ == '__main__':
    main()