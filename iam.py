import boto3
import pandas as pd
from datetime import datetime


# ==========================================================
# AWS CONFIGURATION
# ==========================================================

region = 'ap-south-1'

idstoreclient = boto3.client(
    'identitystore',
    region_name=region
)

ssoadminclient = boto3.client(
    'sso-admin',
    region_name=region
)

orgsclient = boto3.client(
    'organizations',
    region_name=region
)


# ==========================================================
# INITIALIZE DICTIONARIES
# ==========================================================

users = {}
groups = {}
permissionSets = {}
Accounts = {}


# ==========================================================
# GET IAM IDENTITY CENTER INSTANCE
# ==========================================================

Instances = (
    ssoadminclient.list_instances()
).get('Instances')

print("Instances:", Instances)

if not Instances:
    print("No SSO instances found.")
    exit(1)


InstanceARN = Instances[0].get('InstanceArn')

IdentityStoreId = Instances[0].get(
    'IdentityStoreId'
)


# ==========================================================
# REMOVE TIMEZONE FROM AWS DATETIME
# ==========================================================

def remove_timezone(value):
    """
    AWS returns CreatedAt and UpdatedAt as timezone-aware
    datetime objects.

    Excel does not support timezone-aware datetime values,
    so remove the timezone before writing to Excel.
    """

    if isinstance(value, datetime):

        if value.tzinfo is not None:
            return value.replace(
                tzinfo=None
            )

        return value

    return value


# ==========================================================
# MAP USER IDs
# ==========================================================

def mapUserIDs():

    ListUsers = idstoreclient.list_users(
        IdentityStoreId=IdentityStoreId
    )

    ListOfUsers = ListUsers['Users']

    while 'NextToken' in ListUsers.keys():

        ListUsers = idstoreclient.list_users(
            IdentityStoreId=IdentityStoreId,
            NextToken=ListUsers['NextToken']
        )

        ListOfUsers.extend(
            ListUsers['Users']
        )

    # ------------------------------------------------------
    # Store user information
    # ------------------------------------------------------

    for eachUser in ListOfUsers:

        user_id = eachUser.get('UserId')

        users.update({

            user_id: {

                # AWS IAM Identity Center username
                'UserName':
                    eachUser.get(
                        'UserName',
                        'N/A'
                    ),

                # Email
                'Email':
                    eachUser.get('Emails')[0]['Value']
                    if 'Emails' in eachUser
                    and eachUser['Emails']
                    else 'N/A',

                # First name
                'FirstName':
                    eachUser.get(
                        'Name',
                        {}
                    ).get(
                        'GivenName',
                        'N/A'
                    ),

                # Last name
                'LastName':
                    eachUser.get(
                        'Name',
                        {}
                    ).get(
                        'FamilyName',
                        'N/A'
                    ),

                # Display name shown in AWS Console
                'DisplayName':
                    eachUser.get(
                        'DisplayName',
                        'N/A'
                    ),

                # Enabled / Disabled
                'Status':
                    eachUser.get(
                        'UserStatus',
                        'N/A'
                    ),

                # AWS Identity Center Created date
                'Created_date':
                    remove_timezone(
                        eachUser.get(
                            'CreatedAt'
                        )
                    ),

                # AWS Identity Center Updated date
                'Last_update':
                    remove_timezone(
                        eachUser.get(
                            'UpdatedAt'
                        )
                    )
            }
        })

    print(
        f"Total Identity Center users mapped: "
        f"{len(users)}"
    )


# ==========================================================
# MAP GROUP IDs
# ==========================================================

def mapGroupIDs():

    ListGroups = idstoreclient.list_groups(
        IdentityStoreId=IdentityStoreId
    )

    ListOfGroups = ListGroups['Groups']

    while 'NextToken' in ListGroups.keys():

        ListGroups = idstoreclient.list_groups(
            IdentityStoreId=IdentityStoreId,
            NextToken=ListGroups['NextToken']
        )

        ListOfGroups.extend(
            ListGroups['Groups']
        )

    for eachGroup in ListOfGroups:

        groups.update({
            eachGroup.get('GroupId'):
                eachGroup.get('DisplayName')
        })

    print(
        f"Total groups mapped: "
        f"{len(groups)}"
    )


# ==========================================================
# MAP PERMISSION SET IDs
# ==========================================================

def mapPermissionSetIDs():

    ListPermissionSets = (
        ssoadminclient.list_permission_sets(
            InstanceArn=InstanceARN
        )
    )

    ListOfPermissionSets = (
        ListPermissionSets['PermissionSets']
    )

    while 'NextToken' in ListPermissionSets.keys():

        ListPermissionSets = (
            ssoadminclient.list_permission_sets(
                InstanceArn=InstanceARN,
                NextToken=ListPermissionSets[
                    'NextToken'
                ]
            )
        )

        ListOfPermissionSets.extend(
            ListPermissionSets['PermissionSets']
        )

    for eachPermissionSet in ListOfPermissionSets:

        permissionSetDescription = (
            ssoadminclient.describe_permission_set(
                InstanceArn=InstanceARN,
                PermissionSetArn=eachPermissionSet
            )
        )

        permissionSetDetails = (
            permissionSetDescription.get(
                'PermissionSet'
            )
        )

        permissionSets.update({

            permissionSetDetails.get(
                'PermissionSetArn'
            ):

                permissionSetDetails.get(
                    'Name'
                )
        })

    print(
        f"Total permission sets mapped: "
        f"{len(permissionSets)}"
    )


# ==========================================================
# LIST PERMISSION SETS PROVISIONED TO ACCOUNT
# ==========================================================

def GetPermissionSetsProvisionedToAccount(
    AccountID
):

    PermissionSetsProvisionedToAccount = (
        ssoadminclient
        .list_permission_sets_provisioned_to_account(
            InstanceArn=InstanceARN,
            AccountId=AccountID
        )
    )

    ListOfPermissionSetsProvisionedToAccount = (
        PermissionSetsProvisionedToAccount[
            'PermissionSets'
        ]
    )

    while (
        'NextToken'
        in PermissionSetsProvisionedToAccount.keys()
    ):

        PermissionSetsProvisionedToAccount = (
            ssoadminclient
            .list_permission_sets_provisioned_to_account(
                InstanceArn=InstanceARN,
                AccountId=AccountID,
                NextToken=
                    PermissionSetsProvisionedToAccount[
                        'NextToken'
                    ]
            )
        )

        ListOfPermissionSetsProvisionedToAccount.extend(
            PermissionSetsProvisionedToAccount[
                'PermissionSets'
            ]
        )

    return ListOfPermissionSetsProvisionedToAccount


# ==========================================================
# GET GROUP MEMBERS
# ==========================================================

def getGroupMembers(group_id):

    memberships = []

    ListGroupMemberships = (
        idstoreclient.list_group_memberships(
            GroupId=group_id,
            IdentityStoreId=IdentityStoreId
        )
    )

    memberships.extend(
        ListGroupMemberships[
            'GroupMemberships'
        ]
    )

    while 'NextToken' in ListGroupMemberships.keys():

        ListGroupMemberships = (
            idstoreclient.list_group_memberships(
                GroupId=group_id,
                IdentityStoreId=IdentityStoreId,
                NextToken=
                    ListGroupMemberships[
                        'NextToken'
                    ]
            )
        )

        memberships.extend(
            ListGroupMemberships[
                'GroupMemberships'
            ]
        )

    member_details = []

    for membership in memberships:

        user_id = (
            membership[
                'MemberId'
            ][
                'UserId'
            ]
        )

        user_info = users.get(
            user_id,
            {}
        )

        member_details.append({

            'UserId':
                user_id,

            'UserName':
                user_info.get(
                    'UserName',
                    'N/A'
                ),

            'Email':
                user_info.get(
                    'Email',
                    'N/A'
                ),

            'FirstName':
                user_info.get(
                    'FirstName',
                    'N/A'
                ),

            'LastName':
                user_info.get(
                    'LastName',
                    'N/A'
                ),

            'DisplayName':
                user_info.get(
                    'DisplayName',
                    'N/A'
                ),

            'Status':
                user_info.get(
                    'Status',
                    'N/A'
                ),

            'Created_date':
                user_info.get(
                    'Created_date'
                ),

            'Last_update':
                user_info.get(
                    'Last_update'
                )
        })

    return member_details


# ==========================================================
# DEFINE PERMISSION TYPE
# ==========================================================

def getPermissionType(
    permission_set
):

    if permission_set is None:
        return "Read and Write"

    if "Read" in permission_set:

        return "Read"

    elif "Write" in permission_set:

        return "Write"

    else:

        return "Read and Write"


# ==========================================================
# LIST ACCOUNT ASSIGNMENTS
# ==========================================================

def ListAccountAssignments(
    AccountID
):

    PermissionSetsList = (
        GetPermissionSetsProvisionedToAccount(
            AccountID
        )
    )

    Assignments = []

    for permissionSet in PermissionSetsList:

        AccountAssignments = (
            ssoadminclient.list_account_assignments(
                InstanceArn=InstanceARN,
                AccountId=AccountID,
                PermissionSetArn=permissionSet
            )
        )

        Assignments.extend(
            AccountAssignments[
                'AccountAssignments'
            ]
        )

        while 'NextToken' in AccountAssignments.keys():

            AccountAssignments = (
                ssoadminclient.list_account_assignments(
                    InstanceArn=InstanceARN,
                    AccountId=AccountID,
                    PermissionSetArn=permissionSet,
                    NextToken=
                        AccountAssignments[
                            'NextToken'
                        ]
                )
            )

            Assignments.extend(
                AccountAssignments[
                    'AccountAssignments'
                ]
            )

    return Assignments


# ==========================================================
# WRITE DATA TO EXCEL
# ==========================================================

def writeToExcel():

    # ======================================================
    # AWS ACCOUNT IDs
    # ======================================================

    account_ids = [

        '841162697528',

        '796973490964',

        '677276097730',

        '051826701503',

        '557690580823'
    ]

    # ======================================================
    # OUTPUT FILE
    # ======================================================

    output_file = (
        'IAM_v2_user_permissions_September_2026.xlsx'
    )

    # ======================================================
    # CREATE EXCEL WORKBOOK
    # ======================================================

    with pd.ExcelWriter(
        output_file,
        engine='openpyxl'
    ) as writer:

        # ==================================================
        # PROCESS EACH AWS ACCOUNT
        # ==================================================

        for specific_account_id in account_ids:

            print(
                f"\nProcessing AWS Account: "
                f"{specific_account_id}"
            )

            # ----------------------------------------------
            # Store output by username
            # ----------------------------------------------

            output_data = {}

            # ----------------------------------------------
            # Get account assignments
            # ----------------------------------------------

            GetAccountAssignments = (
                ListAccountAssignments(
                    specific_account_id
                )
            )

            # ==================================================
            # PROCESS ASSIGNMENTS
            # ==================================================

            for eachAssignment in GetAccountAssignments:

                permission_set_name = (
                    permissionSets.get(
                        eachAssignment.get(
                            'PermissionSetArn'
                        )
                    )
                )

                permission_type = (
                    getPermissionType(
                        permission_set_name
                    )
                )

                # ------------------------------------------
                # Read permission
                # ------------------------------------------

                read_permission = (

                    'Read'

                    if permission_type == 'Read'

                    or permission_type ==
                    'Read and Write'

                    else ''
                )

                # ------------------------------------------
                # Write permission
                # ------------------------------------------

                write_permission = (

                    'Write'

                    if permission_type == 'Write'

                    or permission_type ==
                    'Read and Write'

                    else ''
                )

                # ==================================================
                # GROUP ASSIGNMENT
                # ==================================================

                if (
                    eachAssignment.get(
                        'PrincipalType'
                    )
                    == 'GROUP'
                ):

                    group_id = (
                        eachAssignment.get(
                            'PrincipalId'
                        )
                    )

                    group_name = (
                        groups.get(
                            group_id,
                            'Unknown Group'
                        )
                    )

                    group_members = (
                        getGroupMembers(
                            group_id
                        )
                    )

                    # ------------------------------------------
                    # Add every group member
                    # ------------------------------------------

                    for member in group_members:

                        username = (
                            member.get(
                                'UserName'
                            )
                        )

                        if not username:
                            continue

                        # --------------------------------------
                        # Create user record
                        # --------------------------------------

                        if username not in output_data:

                            output_data[username] = {

                                'UserName':
                                    username,

                                'DisplayName':
                                    member.get(
                                        'DisplayName',
                                        'N/A'
                                    ),

                                'Email':
                                    member.get(
                                        'Email',
                                        'N/A'
                                    ),

                                'FirstName':
                                    member.get(
                                        'FirstName',
                                        'N/A'
                                    ),

                                'LastName':
                                    member.get(
                                        'LastName',
                                        'N/A'
                                    ),

                                'Status':
                                    member.get(
                                        'Status',
                                        'N/A'
                                    ),

                                'Created_date':
                                    member.get(
                                        'Created_date'
                                    ),

                                'Last_update':
                                    member.get(
                                        'Last_update'
                                    ),

                                'PermissionSets':
                                    [],

                                'PermissionTypeRead':
                                    read_permission,

                                'PermissionTypeWrite':
                                    write_permission,

                                'Organization':
                                    (
                                        'accenture'

                                        if member.get(
                                            'Email',
                                            ''
                                        ).endswith(
                                            '@accenture.com'
                                        )

                                        else 'iocl'

                                        if member.get(
                                            'Email',
                                            ''
                                        ).endswith(
                                            '@indianoil.in'
                                        )

                                        else 'N/A'
                                    )
                            }

                        else:

                            # ----------------------------------
                            # Update permission flags
                            # ----------------------------------

                            if read_permission:

                                output_data[
                                    username
                                ][
                                    'PermissionTypeRead'
                                ] = 'Read'

                            if write_permission:

                                output_data[
                                    username
                                ][
                                    'PermissionTypeWrite'
                                ] = 'Write'

                        # --------------------------------------
                        # Add permission set
                        # --------------------------------------

                        if permission_set_name:

                            output_data[
                                username
                            ][
                                'PermissionSets'
                            ].append(
                                permission_set_name
                            )

                # ==================================================
                # DIRECT USER ASSIGNMENT
                # ==================================================

                else:

                    user_info = users.get(

                        eachAssignment.get(
                            'PrincipalId'
                        ),

                        {}
                    )

                    username = (
                        user_info.get(
                            'UserName'
                        )
                    )

                    if not username:
                        continue

                    # ------------------------------------------
                    # Create user record
                    # ------------------------------------------

                    if username not in output_data:

                        output_data[username] = {

                            'UserName':
                                username,

                            'DisplayName':
                                user_info.get(
                                    'DisplayName',
                                    'N/A'
                                ),

                            'Email':
                                user_info.get(
                                    'Email',
                                    'N/A'
                                ),

                            'FirstName':
                                user_info.get(
                                    'FirstName',
                                    'N/A'
                                ),

                            'LastName':
                                user_info.get(
                                    'LastName',
                                    'N/A'
                                ),

                            'Status':
                                user_info.get(
                                    'Status',
                                    'N/A'
                                ),

                            'Created_date':
                                user_info.get(
                                    'Created_date'
                                ),

                            'Last_update':
                                user_info.get(
                                    'Last_update'
                                ),

                            'PermissionSets':
                                [],

                            'PermissionTypeRead':
                                read_permission,

                            'PermissionTypeWrite':
                                write_permission,

                            'Organization':
                                (
                                    'accenture'

                                    if user_info.get(
                                        'Email',
                                        ''
                                    ).endswith(
                                        '@accenture.com'
                                    )

                                    else 'iocl'

                                    if user_info.get(
                                        'Email',
                                        ''
                                    ).endswith(
                                        '@indianoil.in'
                                    )

                                    else 'N/A'
                                )
                        }

                    else:

                        # --------------------------------------
                        # Update permission flags
                        # --------------------------------------

                        if read_permission:

                            output_data[
                                username
                            ][
                                'PermissionTypeRead'
                            ] = 'Read'

                        if write_permission:

                            output_data[
                                username
                            ][
                                'PermissionTypeWrite'
                            ] = 'Write'

                    # ------------------------------------------
                    # Add permission set
                    # ------------------------------------------

                    if permission_set_name:

                        output_data[
                            username
                        ][
                            'PermissionSets'
                        ].append(
                            permission_set_name
                        )

            # ==================================================
            # PREPARE EXCEL OUTPUT
            # ==================================================

            final_output = []

            for user, data in output_data.items():

                # ----------------------------------------------
                # Remove duplicate permission sets
                # ----------------------------------------------

                permission_set_list = list(
                    dict.fromkeys(
                        data.get(
                            'PermissionSets',
                            []
                        )
                    )
                )

                final_output.append({

                    'UserName':
                        data.get(
                            'UserName',
                            ''
                        ),

                    'DisplayName':
                        data.get(
                            'DisplayName',
                            ''
                        ),

                    'Email':
                        data.get(
                            'Email',
                            ''
                        ),

                    'FirstName':
                        data.get(
                            'FirstName',
                            ''
                        ),

                    'LastName':
                        data.get(
                            'LastName',
                            ''
                        ),

                    'Status':
                        data.get(
                            'Status',
                            ''
                        ),

                    'Permission Type (Read)':
                        data.get(
                            'PermissionTypeRead',
                            ''
                        ),

                    'Permission Type (Write)':
                        data.get(
                            'PermissionTypeWrite',
                            ''
                        ),

                    'Permission Sets':
                        '\n'.join(
                            permission_set_list
                        ),

                    'Organization':
                        data.get(
                            'Organization',
                            ''
                        ),

                    'Created date':
                        data.get(
                            'Created_date',
                            ''
                        ),

                    'Last updated':
                        data.get(
                            'Last_update',
                            ''
                        )
                })

            # ==================================================
            # CREATE DATAFRAME
            # ==================================================

            df = pd.DataFrame(
                final_output
            )

            # ==================================================
            # DETERMINE SHEET NAME
            # ==================================================

            if specific_account_id == "841162697528":

                sheet_name = "Dev_account"

            elif specific_account_id == "796973490964":

                sheet_name = "SharedService_account"

            elif specific_account_id == "677276097730":

                sheet_name = "Prod_account"

            elif specific_account_id == "051826701503":

                sheet_name = "Devops_account"

            elif specific_account_id == "557690580823":

                sheet_name = "PreProd_account"

            else:

                sheet_name = (
                    specific_account_id[:31]
                )

            # ==================================================
            # WRITE ACCOUNT SHEET
            # ==================================================

            df.to_excel(

                writer,

                sheet_name=sheet_name,

                index=False
            )

            print(
                f"Completed: "
                f"{specific_account_id} "
                f"({len(df)} users)"
            )

        # ======================================================
        # IAM IDENTITY CENTER - ALL USERS
        # ======================================================

        print(
            "\nCreating Total_Users sheet..."
        )

        identity_center_users = []

        for user_id, user_info in users.items():

            identity_center_users.append({

                'Username':
                    user_info.get(
                        'UserName',
                        'N/A'
                    ),

                'Display name':
                    user_info.get(
                        'DisplayName',
                        'N/A'
                    ),

                'Status':
                    user_info.get(
                        'Status',
                        'N/A'
                    ),

                'Created date':
                    user_info.get(
                        'Created_date',
                        'N/A'
                    ),

                'Last updated':
                    user_info.get(
                        'Last_update',
                        'N/A'
                    )
            })

        # ======================================================
        # CREATE DATAFRAME FOR ALL USERS
        # ======================================================

        identity_center_df = pd.DataFrame(
            identity_center_users
        )

        # ======================================================
        # WRITE TOTAL USERS SHEET
        # ======================================================

        identity_center_df.to_excel(

            writer,

            sheet_name='Total_Users',

            index=False
        )

        print(
            f"Total_Users sheet created "
            f"({len(identity_center_df)} users)"
        )

    # ==========================================================
    # FINAL MESSAGE
    # ==========================================================

    print(
        f"\nExcel report created successfully: "
        f"{output_file}"
    )


# ==========================================================
# EXECUTE FUNCTIONS
# ==========================================================

mapUserIDs()

mapGroupIDs()

mapPermissionSetIDs()

writeToExcel()