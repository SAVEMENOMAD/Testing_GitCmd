import boto3
import pandas as pd

# Initialize clients with the specified region
region = 'ap-south-1'  # Specify your desired region

idstoreclient = boto3.client('identitystore', region_name=region)
ssoadminclient = boto3.client('sso-admin', region_name=region)
orgsclient = boto3.client('organizations', region_name=region)

# Initialize dictionaries
users = {}
groups = {}
permissionSets = {}
Accounts = {}

# Get the SSO instance and Identity Store ID
Instances = (ssoadminclient.list_instances()).get('Instances')
print("Instances:", Instances)  # Debugging line
if not Instances:
    print("No SSO instances found.")
    exit(1)  # Exit the script if no instances are found

# Extract instance ARN and identity store ID
InstanceARN = Instances[0].get('InstanceArn')
IdentityStoreId = Instances[0].get('IdentityStoreId')

# Dictionary mapping User IDs to usernames
def mapUserIDs():
    ListUsers = idstoreclient.list_users(IdentityStoreId=IdentityStoreId)
    ListOfUsers = ListUsers['Users']
    while 'NextToken' in ListUsers.keys():
        ListUsers = idstoreclient.list_users(IdentityStoreId=IdentityStoreId, NextToken=ListUsers['NextToken'])
        ListOfUsers.extend(ListUsers['Users'])
    
    # Updating users dictionary to store multiple user attributes
    for eachUser in ListOfUsers:
        users.update({
            eachUser.get('UserId'): {
                'UserName': eachUser.get('UserName'),
                'Email': eachUser.get('Emails')[0]['Value'] if 'Emails' in eachUser and eachUser['Emails'] else 'N/A',
                'FirstName': eachUser.get('Name', {}).get('GivenName', 'N/A'),
                'LastName': eachUser.get('Name', {}).get('FamilyName', 'N/A')
            }
        })

# Dictionary mapping Group IDs to display names
def mapGroupIDs():
    ListGroups = idstoreclient.list_groups(IdentityStoreId=IdentityStoreId)
    ListOfGroups = ListGroups['Groups']
    while 'NextToken' in ListGroups.keys():
        ListGroups = idstoreclient.list_groups(IdentityStoreId=IdentityStoreId, NextToken=ListGroups['NextToken'])
        ListOfGroups.extend(ListGroups['Groups'])
    for eachGroup in ListOfGroups:
        groups.update({eachGroup.get('GroupId'): eachGroup.get('DisplayName')})

# Dictionary mapping permission set ARNs to permission set names
def mapPermissionSetIDs():
    ListPermissionSets = ssoadminclient.list_permission_sets(InstanceArn=InstanceARN)
    ListOfPermissionSets = ListPermissionSets['PermissionSets']
    while 'NextToken' in ListPermissionSets.keys():
        ListPermissionSets = ssoadminclient.list_permission_sets(InstanceArn=InstanceARN, NextToken=ListPermissionSets['NextToken'])
        ListOfPermissionSets.extend(ListPermissionSets['PermissionSets'])
    for eachPermissionSet in ListOfPermissionSets:
        permissionSetDescription = ssoadminclient.describe_permission_set(InstanceArn=InstanceARN, PermissionSetArn=eachPermissionSet)
        permissionSetDetails = permissionSetDescription.get('PermissionSet')
        permissionSets.update({permissionSetDetails.get('PermissionSetArn'): permissionSetDetails.get('Name')})

# Listing Permission sets provisioned to an account
def GetPermissionSetsProvisionedToAccount(AccountID):
    PermissionSetsProvisionedToAccount = ssoadminclient.list_permission_sets_provisioned_to_account(InstanceArn=InstanceARN, AccountId=AccountID)
    ListOfPermissionSetsProvisionedToAccount = PermissionSetsProvisionedToAccount['PermissionSets']
    while 'NextToken' in PermissionSetsProvisionedToAccount.keys():
        PermissionSetsProvisionedToAccount = ssoadminclient.list_permission_sets_provisioned_to_account(InstanceArn=InstanceARN, AccountId=AccountID, NextToken=PermissionSetsProvisionedToAccount['NextToken'])
        ListOfPermissionSetsProvisionedToAccount.extend(PermissionSetsProvisionedToAccount['PermissionSets'])
    return ListOfPermissionSetsProvisionedToAccount

# Get the members of a group
def getGroupMembers(group_id):
    memberships = []
    ListGroupMemberships = idstoreclient.list_group_memberships(GroupId=group_id, IdentityStoreId=IdentityStoreId)
    memberships.extend(ListGroupMemberships['GroupMemberships'])
    while 'NextToken' in ListGroupMemberships.keys():
        ListGroupMemberships = idstoreclient.list_group_memberships(GroupId=group_id, IdentityStoreId=IdentityStoreId, NextToken=ListGroupMemberships['NextToken'])
        memberships.extend(ListGroupMemberships['GroupMemberships'])
    
    member_details = []
    for membership in memberships:
        user_id = membership['MemberId']['UserId']
        user_info = users.get(user_id, {})
        member_details.append({
            'UserId': user_info.get('UserId'),
            'UserName': user_info.get('UserName'),
            'Email': user_info.get('Email'),
            'FirstName': user_info.get('FirstName', 'N/A'),
            'LastName': user_info.get('LastName', 'N/A')
        })
    
    return member_details

# Define Permission Type (Read, Write, or Both)
def getPermissionType(permission_set):
    # Placeholder logic for permission type, based on the permission set name
    if "Read" in permission_set:
        return "Read"
    elif "Write" in permission_set:
        return "Write"
    else:
        return "Read and Write"

# To retrieve the assignment of each permissionset/user/group/account assignment
def ListAccountAssignments(AccountID):
    PermissionSetsList = GetPermissionSetsProvisionedToAccount(AccountID)
    Assignments = []
    for permissionSet in PermissionSetsList:
        AccountAssignments = ssoadminclient.list_account_assignments(InstanceArn=InstanceARN, AccountId=AccountID, PermissionSetArn=permissionSet)
        Assignments.extend(AccountAssignments['AccountAssignments'])
        while 'NextToken' in AccountAssignments.keys():
            AccountAssignments = ssoadminclient.list_account_assignments(InstanceArn=InstanceARN, AccountId=AccountID, PermissionSetArn=permissionSet, NextToken=AccountAssignments['NextToken'])
            Assignments.extend(AccountAssignments['AccountAssignments'])
    return Assignments

# To store the output in an Excel file
def writeToExcel():

    # ==========================================================
    # ADD AWS ACCOUNT IDs HERE
    # ==========================================================

    account_ids = [
        '841162697528',
        '796973490964',
        '677276097730',
        '051826701503',
        '557690580823'
    ]

    # Name of the single Excel file
    output_file = 'IAM_v2_user_permissions_September_2026.xlsx'

    # Create one Excel workbook
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:

        # Loop through each AWS account
        for specific_account_id in account_ids:

            print(f"\nProcessing AWS Account: {specific_account_id}")

            # Collect data
            output_data = {}

            GetAccountAssignments = ListAccountAssignments(
                specific_account_id
            )

            for eachAssignment in GetAccountAssignments:

                permission_set_name = permissionSets.get(
                    eachAssignment.get('PermissionSetArn')
                )

                permission_type = getPermissionType(
                    permission_set_name
                )

                # Split the permission type into Read and Write
                read_permission = (
                    'Read'
                    if permission_type == 'Read'
                    or permission_type == 'Read and Write'
                    else ''
                )

                write_permission = (
                    'Write'
                    if permission_type == 'Write'
                    or permission_type == 'Read and Write'
                    else ''
                )

                # ==================================================
                # GROUP ASSIGNMENT
                # ==================================================

                if eachAssignment.get('PrincipalType') == 'GROUP':

                    group_id = eachAssignment.get('PrincipalId')

                    group_name = groups.get(
                        group_id,
                        'Unknown Group'
                    )

                    group_members = getGroupMembers(group_id)

                    for member in group_members:

                        username = member.get('UserName')

                        if username not in output_data:

                            output_data[username] = {
                                'UserName': username,
                                'Email': member.get('Email'),
                                'FirstName': member.get(
                                    'FirstName',
                                    'N/A'
                                ),
                                'LastName': member.get(
                                    'LastName',
                                    'N/A'
                                ),
                                'PermissionSets': [],
                                'PermissionTypeRead':
                                    read_permission,
                                'PermissionTypeWrite':
                                    write_permission,
                                'Organization':
                                    'accenture'
                                    if member.get(
                                        'Email',
                                        ''
                                    ).endswith('@accenture.com')
                                    else 'iocl'
                                    if member.get(
                                        'Email',
                                        ''
                                    ).endswith('@indianoil.in')
                                    else 'N/A'
                            }

                        output_data[username][
                            'PermissionSets'
                        ].append(permission_set_name)

                # ==================================================
                # DIRECT USER ASSIGNMENT
                # ==================================================

                else:

                    user_info = users.get(
                        eachAssignment.get('PrincipalId'),
                        {}
                    )

                    username = user_info.get('UserName')

                    if username not in output_data:

                        output_data[username] = {
                            'UserName': username,
                            'Email': user_info.get('Email'),
                            'FirstName': user_info.get(
                                'FirstName',
                                'N/A'
                            ),
                            'LastName': user_info.get(
                                'LastName',
                                'N/A'
                            ),
                            'PermissionSets': [],
                            'PermissionTypeRead':
                                read_permission,
                            'PermissionTypeWrite':
                                write_permission,
                            'Organization':
                                'accenture'
                                if user_info.get(
                                    'Email',
                                    ''
                                ).endswith('@accenture.com')
                                else 'iocl'
                                if user_info.get(
                                    'Email',
                                    ''
                                ).endswith('@indianoil.in')
                                else 'N/A'
                        }

                    output_data[username][
                        'PermissionSets'
                    ].append(permission_set_name)

            # ======================================================
            # PREPARE EXCEL OUTPUT
            # ======================================================

            final_output = []

            for user, data in output_data.items():

                final_output.append({

                    'UserName':
                        data['UserName'],

                    'Email':
                        data['Email'],

                    'FirstName':
                        data['FirstName'],

                    'LastName':
                        data['LastName'],

                    'Permission Type (Read)':
                        data['PermissionTypeRead'],

                    'Permission Type (Write)':
                        data['PermissionTypeWrite'],

                    'Permission Sets':
                        '\n'.join(
                            data['PermissionSets']
                        ),

                    'Organization':
                        data['Organization']
                })

            # Create DataFrame
            df = pd.DataFrame(final_output)

            # ======================================================
            # CREATE SHEET FOR THIS ACCOUNT
            # ======================================================
        # '841162697528 - > Developement',
        # '796973490964' - > SharedService,
        # '677276097730'  -> Prod,
        # '051826701503', ->Devops
        # '557690580823' -> PreProd
            if specific_account_id == "841162697528":
                sheet_name = f"Dev_account"

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                print(
                    f"Completed: {specific_account_id} "
                    f"({len(df)} users)"
                )
            elif specific_account_id == "796973490964":
                sheet_name = f"SharedService_account"

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                print(
                    f"Completed: {specific_account_id} "
                    f"({len(df)} users)"
                )
            elif specific_account_id == "677276097730":
                sheet_name = f"Prod_account"

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                print(
                    f"Completed: {specific_account_id} "
                    f"({len(df)} users)"
                )
            elif specific_account_id == "051826701503":
                sheet_name = f"Devops_account"

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                print(
                    f"Completed: {specific_account_id} "
                    f"({len(df)} users)"
                )
            elif specific_account_id == "557690580823":
                sheet_name = f"PreProd_account"

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

            print(
                f"Completed: {specific_account_id} "
                f"({len(df)} users)"
            )
    

    print(
        f"\nExcel report created successfully: {output_file}"
    )
# Execute all functions
mapUserIDs()
mapGroupIDs()
mapPermissionSetIDs()
writeToExcel()
