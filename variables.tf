variable "name" {
  description = "The name of the pipeline"
}

variable "allowed_accounts" {
  description = "The account numbers allowed to post to the pipeline"
}

variable "fallback_sns" {
  description = "The SNS topic arn to post any lambda failures to"
}
