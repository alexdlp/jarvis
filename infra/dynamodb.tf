# The store.
#
# One DynamoDB table, currently storing a single entity type: work items.
# Blocks, credentials and planning state are listed as planned features in the
# README but are deliberately not modelled yet. Their access patterns should be
# known before their key shape is committed.
#
# DynamoDB only requires schema declarations for attributes used as table or
# index keys. Attributes such as title, deadline, tags and description are
# the application and therefore do not appear as attribute blocks here.
#
# docs/data-model.md documents the complete work-item representation and how
# these four key attributes are derived.

resource "aws_dynamodb_table" "main" {
  name = "jarvis-dynamodb"

  # On-demand capacity matches this workload well: long idle periods followed
  # by short bursts of assistant activity. With PAY_PER_REQUEST there is no
  # provisioned throughput to pay for while the application is idle, and no
  # application-managed autoscaling policy is required.
  billing_mode = "PAY_PER_REQUEST"

  # These stay as hash_key/range_key despite the deprecation warning, because
  # aws 6.62.0 offers no table-level key_schema block to move them to — the
  # replacement exists only inside global_secondary_index. Revisit when the
  # provider grows one.
  hash_key  = "pk"
  range_key = "sk"

  # All keys are strings because they are composed from prefixes, identifiers
  # and ISO-8601 timestamps.
  #
  # Timestamp ordering only works lexicographically when every timestamp uses
  # the same canonical representation, for example UTC with the same precision:
  #
  #   2026-09-19T15:30:00Z
  #
  # The application is responsible for enforcing that representation.
  attribute {
    name = "pk"
    type = "S"
  }

  # The base-table sort key is intentional even though only one entity type
  # exists today.
  #
  # A table's primary-key schema cannot be modified in place. Introducing a
  # sort key later would require creating a replacement table and migrating the
  # data. Having it now also reserves a clean namespace for additional entity
  # types:
  #
  #   ITEM#<id>
  #   BLOCK#...
  #   CREDENTIAL#...
  #
  # With the current model, begins_with(sk, "ITEM#") selects the contiguous
  # range containing work items for a user. It does not imply chronological
  # ordering: ITEM# values are ordered lexicographically by the item identifier.
  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "status_pk"
    type = "S"
  }

  attribute {
    name = "status_sk"
    type = "S"
  }

  # Access work items by lifecycle phase and status.
  #
  #   status_pk = U#<sub>#open
  #             | U#<sub>#closed
  #
  # where:
  #
  #   open   = inbox, active, parked
  #   closed = done, cancelled
  #
  # and:
  #
  #   status_sk = <status>#<relevant-date>
  #
  # Examples:
  #
  #   U#abc#open   / active#2026-09-20T10:00:00Z
  #   U#abc#open   / parked#2026-09-25T08:00:00Z
  #   U#abc#closed / done#2026-09-18T17:42:00Z
  #
  # The phase is in the partition key so that "all open work" is a single Query.
  # It could not be, otherwise: sorted lexicographically the open statuses are
  # not contiguous, because cancelled and done fall between active and inbox.
  #
  # Note what this is NOT for. Sharing a partition with the history would not
  # make the active query traverse it: a sort key condition seeks, and DynamoDB
  # charges for the items matching the key condition rather than for the ones it
  # skipped past to reach them. Only a FilterExpression reads and discards.
  #
  # The status prefix in status_sk also makes an individual status a
  # contiguous range:
  #
  #   begins_with(status_sk, "active#")
  #
  # Note that the prefix determines the primary ordering. A Query over the whole
  # open partition returns items grouped lexicographically by status and then by
  # date within each status. It does NOT provide one global chronological order
  # across inbox, active and parked.
  #
  # status_pk and status_sk are mutable index keys. Closing an item
  # changes its GSI key, and DynamoDB applies that as two index operations —
  # removing the previous entry and inserting the new one — in addition to the
  # write against the base table.
  #
  # This is currently the only GSI because it implements a known access pattern.
  # Additional GSIs can be added to an existing table later when new access
  # patterns are known; there is no reason to speculate about them now.
  global_secondary_index {
    name = "status"

    # key_schema rather than the hash_key/range_key pair the provider now warns
    # about. It mirrors the DynamoDB API, where a key schema has always been an
    # ordered list of (attribute, role) rather than two named arguments.
    #
    # Done now because the table does not exist yet, so it is a pure edit to the
    # configuration. Changing how an index declares its keys once the index is
    # live is a different proposition.
    key_schema {
      attribute_name = "status_pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "status_sk"
      key_type       = "RANGE"
    }

    # INCLUDE keeps list queries index-only without duplicating the potentially
    # unbounded `description` attribute into every index entry.
    #
    # DynamoDB automatically projects the base-table primary key and the GSI key
    # attributes. The attributes below are the additional fields required by
    # work-item list views.
    projection_type = "INCLUDE"

    non_key_attributes = [
      "entity",
      "title",
      "kind",
      "status",
      "importance",
      "deadline",
      "estimate_minutes",
      "parent_id",
      "tags",
      "completed_at",
      "version",
    ]
  }

  # No local secondary indexes.
  #
  # LSIs must be defined when the table is created and cannot be added later.
  # They also impose DynamoDB's 10 GB item-collection limit for each base-table
  # partition-key value.
  #
  # Because all data belonging to one user shares the same base-table partition
  # key, avoiding LSIs removes that per-user item-collection ceiling.
  #
  # New query patterns should therefore use GSIs unless a future requirement
  # specifically justifies an LSI.

  # No item currently expires, but TTL support is enabled in advance.
  #
  # DynamoDB only acts on items that contain `expires_at`; items without the
  # attribute are unaffected. If TTL is introduced later, the application must
  # write expires_at as a Unix epoch timestamp in seconds.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # Continuous point-in-time recovery protects against accidental application
  # writes, deletes and bad migrations.
  #
  # DynamoDB supports a recovery window from 1 to 35 days. Set 35 explicitly so
  # the desired retention is part of the infrastructure definition rather than
  # relying on the service default.
  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 35
  }

  # DynamoDB encrypts all tables at rest by default using an AWS-owned key.
  #
  # Enabling server-side encryption here without specifying kms_key_arn selects
  # the AWS-managed DynamoDB KMS key, alias/aws/dynamodb.
  #
  # Compared with the default AWS-owned key, the AWS-managed key is visible in
  # this account and its KMS usage can be audited through CloudTrail. AWS KMS
  # charges and quotas apply.
  #
  # DynamoDB uses envelope encryption and caches its table key, so this does not
  # imply one KMS Decrypt request per DynamoDB read or write.
  server_side_encryption {
    enabled = true
  }

  # Keep deletion protection disabled while destroying and recreating the
  # development stack is expected behaviour.
  #
  # Enable this once the table contains persistent data that should survive an
  # accidental `terraform destroy`. At that point a destroy must explicitly
  # disable protection before DynamoDB will allow the table to be deleted.
  deletion_protection_enabled = false

  tags = {
    Application = "jarvis"
  }
}


# Runtime access to the DynamoDB data plane.
#
# Use an application-specific inline policy rather than an AWS-managed
# DynamoDB policy so the Lambda can operate only on this table and its indexes.
#
# Scan is intentionally omitted. Every currently defined access pattern is
# implemented with GetItem, BatchGetItem or Query. If application code
# accidentally attempts a Scan, IAM rejects it instead of allowing an
# inefficient full-table access pattern to become established.
#
# Control-plane permissions such as CreateTable, UpdateTable and DeleteTable are
# also intentionally absent. Terraform owns the table's infrastructure.

resource "aws_iam_role_policy" "dynamodb" {
  name = "jarvis-dynamodb-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [{
      Effect = "Allow"

      Action = [
        "dynamodb:GetItem",
        "dynamodb:BatchGetItem",
        "dynamodb:Query",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:TransactGetItems",
        "dynamodb:TransactWriteItems",
        "dynamodb:ConditionCheckItem",
      ]

      # Include both the table ARN and its index ARNs.
      #
      # Operations against the base table are authorised against the table ARN.
      # Querying the `status` GSI is authorised against that index's ARN.
      #
      # Using index/* avoids changing this IAM policy every time Terraform adds
      # another GSI to this same table.
      Resource = [
        aws_dynamodb_table.main.arn,
        "${aws_dynamodb_table.main.arn}/index/*",
      ]
    }]
  })
}
