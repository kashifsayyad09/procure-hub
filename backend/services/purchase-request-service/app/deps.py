from procurehub_common.auth_deps import make_user_auth

get_principal, require_any_permission = make_user_auth(lambda request: request.app.state.settings)
