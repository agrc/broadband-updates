'''
This script automates the broadband feature class update process. 
update_features() deletes the old features from the current feature class (current_data_fc)
    and copies them from the updated feature class (new_data_fc) to the current.
    THE UPDATED FEATURE CLASS MUST HAVE ALL THE DATA (EXISTING + NEW) FOR THAT PROVIDER
It will optionally archive the existing data in the master feature class to an
    archive feature class (archive_fc)
'''

#: Manually create new feature class
#: Archive existing data for provider in BB feature class into archive feature class
#: Delete existing data from BB feature class
#: Copy data from new feature class into BB feature class
#: Delete existing data from SGID feature class
#: Copy data from new feature class into SGID feature class

import sys
import traceback
import uuid

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


def get_provider_name(new_data_fc, current_data_fc, provider_field):
    '''
    Gets the provider name from provider_field in new_data_fc, verifies it exists in current_data_fc

    Returns: Provider name as string
    '''

    #: Get the new provider name from the new feature class
    with arcpy.da.SearchCursor(new_data_fc, provider_field) as name_cursor:
        provider = next(name_cursor)[0]

    #: Make sure new provider is valid
    print('\nChecking if provider is valid...')
    arcpy.AddMessage('\n========\n')
    arcpy.AddMessage('Checking if provider is valid...')
    providers = []
    with arcpy.da.SearchCursor(current_data_fc, provider_field) as scursor:
        for row in scursor:
            if row[0] not in providers:
                providers.append(row[0])

    if provider not in providers:
        raise ValueError(f'{provider} not found in list of existing providers in {current_data_fc}.')

    arcpy.AddMessage(f'Updating data for provider {provider}')

    return provider


def archive_provider(provider_field, current_data_fc, archive_fc, data_round):
    '''
    Add data_round and max download tier (MAXADDNTIA) to provider's current data and copy to archive_fc
    '''

    where = f'"{provider_field}" = \'{provider}\''
    current_data_fields = ['SHAPE@', 'UTProvCode', 'TransTech', 'MAXADDOWN', 
                           'MAXADUP', 'LastEdit', 'LastVerified', 'Identifier']

    #: Apparently, MAXADDNTIA only exists in the archive, not the UBB sde or the SGID.
    archive_fields = ['SHAPE@', 'UTProvCode', 'TransTech', 'MAXADDOWN', 
                      'MAXADUP', 'LastEdit', 'LastVerified', 'Identifier', 
                      'DataRound', 'MAXADDNTIA']

    archive_count = 0

    print(f'\nCopying {provider}\'s current features to archive feature class {archive_fc}...')
    arcpy.AddMessage('\n========\n')
    arcpy.AddMessage(f'Copying {provider}\'s current features to archive feature class {archive_fc}...')

    with arcpy.da.SearchCursor(current_data_fc, current_data_fields, where) as current_data_cursor, arcpy.da.InsertCursor(archive_fc, archive_fields) as archive_cursor:

        for current_row in current_data_cursor:
            #: Build a row from the current data
            transfer_row = list(current_row[:])

            #: Calculate DataRound and MAXADDNTIA
            transfer_row.append(data_round)
            maxaddown = current_row[3]
            transfer_row.append(speedcode(maxaddown))

            #: insert row into archive data via Update Cursor
            archive_cursor.insertRow(transfer_row)
            archive_count += 1

    print(f'{archive_count} features archived from {current_data_fc} to {archive_fc}')
    arcpy.AddMessage(f'{archive_count} features archived from {current_data_fc} to {archive_fc}')


def update_features(provider, provider_field, new_data_fc, current_data_fc):
    '''
    Replaces a broadband provider's data in a current feature class (current_data_fc) with data
    from an update feature class (new_data_fc)

    provider:       The name of the provider; used for SQL clauses for defining what features
                    to delete.
    provider_field: The field containing the provider's name; used for SQL clauses for
                    defining what features to delete.
    new_data_fc:    The new data to load into the current feature class. Must contain
                    all the features for that provider; if they only send new areas,
                    be sure to manually copy the existing areas into new_data_fc before 
                    updating.
    current_data_fc: The provider's existing data in this feature class will be deleted 
                    and the contents of new_data_fc will be written in its place.
    '''
    print('\n###')
    print(f'Updating {current_data_fc}')
    arcpy.AddMessage('\n========\n')
    arcpy.AddMessage(f'Updating {current_data_fc}')
    print('###')

    #: Delete provider's features from current fc
    deleted_records = 0
    print(f'\nDeleting {provider}\'s current features from current feature class {current_data_fc}...')
    arcpy.AddMessage(f'Deleting {provider}\'s current features from current feature class {current_data_fc}...')
    where = f'"{provider_field}" = \'{provider}\''

    with arcpy.da.UpdateCursor(current_data_fc, provider_field, where) as current_data_cursor:
        for row in current_data_cursor:
            current_data_cursor.deleteRow()
            deleted_records += 1

    print(f'{deleted_records} records deleted from {current_data_fc}')
    arcpy.AddMessage(f'{deleted_records} records deleted from {current_data_fc}')
    arcpy.AddMessage('\n--\n')
    
    #: Append new features from local fc to current fc
    copied_records = 0
    print(f'\nCopying new features from {new_data_fc} to current feature class {current_data_fc}...')
    arcpy.AddMessage(f'Copying new features from {new_data_fc} to current feature class {current_data_fc}...')

    with arcpy.da.SearchCursor(new_data_fc, '*') as new_data_cursor, arcpy.da.InsertCursor(current_data_fc, '*') as current_data_cursor:
        for row in new_data_cursor:
            current_data_cursor.insertRow(row)
            copied_records += 1

    arcpy.AddMessage(f'{copied_records} records copied from {new_data_fc} to {current_data_fc}')
    print('\n### Finished ###\n')


def generate_identifiers(new_data_fc):
    '''
    Populates the 'Identifier' field of new_data_fc with a unique identifier using uuid.uuid4. The uuid is upper-cased and wrapped in {}. The 'Identifier' field is created if it is not present already.

    Returns: The number of records updated
    '''

    print(f'\nChecking identifier field...')
    arcpy.AddMessage('\n========\n')
    arcpy.AddMessage('Checking identifier field...')

    fields = [f.name for f in arcpy.ListFields(new_data_fc)]
    if 'Identifier' not in fields:
        print(f'Adding "Identifier" field to {new_data_fc}')
        arcpy.AddMessage(f'Adding "Identifier" field to {new_data_fc}')
        arcpy.AddField_management(new_data_fc, 'Identifier', 'TEXT', field_length=50)

    update_counter = 0
    with arcpy.da.UpdateCursor(new_data_fc, ['Identifier']) as new_data_cursor:
        for row in new_data_cursor:
            #: Triple {{{ needed to escape f-string brackets and give us a single { in the output
            guid = f'{{{str(uuid.uuid4()).upper()}}}'
            row[0] = guid
            new_data_cursor.updateRow(row)
            update_counter += 1

    print(f'Identifier added for {update_counter} records in {new_data_fc}')
    arcpy.AddMessage(f'Identifier added for {update_counter} records in {new_data_fc}')

    return update_counter


if __name__ == '__main__':

    new_data_fc = arcpy.GetParameterAsText(0)
    archive_fc = arcpy.GetParameterAsText(1)
    ubb_fc = arcpy.GetParameterAsText(2)
    sgid_fc = arcpy.GetParameterAsText(3)
    data_round = arcpy.GetParameterAsText(4)
    provider_field = arcpy.GetParameterAsText(5)

    try:
        #: Validate and return provider name
        provider = get_provider_name(new_data_fc, ubb_fc, provider_field)
        #: Generate Identifier for new data
        generate_identifiers(new_data_fc)
        #: Archive existing features
        archive_provider(provider_field, ubb_fc, archive_fc, data_round)
        #: Update UBB feature class
        update_features(provider, provider_field, new_data_fc, ubb_fc)
        #: Update SGID feature class
        update_features(provider, provider_field, new_data_fc, sgid_fc)
    
    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        arcpy.AddMessage('========')
        arcpy.AddMessage(traceback.format_exc())

    except:
        error_message = sys.exc_info()[1]
        arcpy.AddError(error_message)
        arcpy.AddMessage('========')
        arcpy.AddMessage(traceback.format_exc())
