// OIDC config for react-oidc-context
export const OIDC_CONFIG = {
  authority: "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_lT9NOeSPB", // https://cognito-idp.<region>.amazonaws.com/<userPoolId>
  client_id: "29kbhfstuf7h59kkis1ppo4i0j", // your app client id
  redirect_uri: "http://localhost:3000",  // must match callback URL in Cognito
  response_type: "code",
  scope: "openid email profile",
};

// Your Cognito domain (for logout)
export const COGNITO_DOMAIN = "https://eu-central-1lt9noespb.auth.eu-central-1.amazoncognito.com";
// e.g. https://my-domain.auth.eu-central-1.amazoncognito.com
// You can find it in the Cognito User Pool console under "Managed Login" > "Domain".

// Logout redirect (must be in allowed logout URLs)
export const LOGOUT_URI = "http://localhost:3000";

// Express backend
export const API_BASE = "http://localhost:3001";

export const BACKEND_URL="https://cc2025-api-b2btduguh5cmdxbn.northeurope-01.azurewebsites.net"
