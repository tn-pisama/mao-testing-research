terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "ai-discovery-469923"
  region  = "us-central1"
}

# OAuth Consent Screen (Brand)
resource "google_iap_brand" "project_brand" {
  support_email     = "tuomo@pisama.ai"
  application_title = "PISAMA"
  project           = "434388095406"
}

# OAuth Client for Web Application
resource "google_iap_client" "oauth_client" {
  display_name = "PISAMA Production"
  brand        = google_iap_brand.project_brand.name
}

# Output the credentials
output "client_id" {
  value     = google_iap_client.oauth_client.client_id
  sensitive = false
}

output "client_secret" {
  value     = google_iap_client.oauth_client.secret
  sensitive = true
}

output "setup_complete" {
  value = <<-EOT

    ✅ OAuth Client Created Successfully!

    Client ID: ${google_iap_client.oauth_client.client_id}

    Run this to see the secret:
    terraform output -raw client_secret

    Then deploy with:
    cd /Users/tuomonikulainen/mao-testing-research
    ./deploy-google-oauth.sh "${google_iap_client.oauth_client.client_id}" "$(terraform output -raw client_secret)"
  EOT
}
