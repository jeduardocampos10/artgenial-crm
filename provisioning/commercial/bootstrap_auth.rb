# frozen_string_literal: true
# Invoked only by the commercial installer after the shared schema is ready.
ActiveRecord::Base.transaction do
  ActiveRecord::Base.connection.execute('SELECT pg_advisory_xact_lock(73829104)')
  load Rails.root.join('db', 'seeds', 'rbac.rb') unless Role.exists?(key: 'super_admin')
  account = RuntimeConfig.account
  if account
    raise 'Account identity conflict' unless account['name'] == ENV.fetch('INSTALLATION_NAME') &&
                                             account['domain'] == ENV.fetch('FRONTEND_HOST')
  else
    RuntimeConfig.set('account', {
      id: SecureRandom.uuid,
      name: ENV.fetch('INSTALLATION_NAME'),
      domain: ENV.fetch('FRONTEND_HOST'),
      support_email: ENV.fetch('ADMIN_EMAIL'),
      locale: 'pt-BR', status: 'active', features: {}, settings: {}, custom_attributes: {}
    })
  end
  raise 'Account bootstrap failed' unless RuntimeConfig.account

  email = ENV.fetch('ADMIN_EMAIL').downcase
  user = User.from_email(email)
  if user
    raise 'Existing administrator identity conflict' unless user.name == ENV.fetch('ADMIN_NAME') &&
                                                           user.has_role?('super_admin')
  else
    raise 'Existing users require manual review' if User.exists?
    password = ENV.fetch('ADMIN_PASSWORD')
    user = User.create!(name: ENV.fetch('ADMIN_NAME'), email: email, password: password,
                        password_confirmation: password, provider: 'email', uid: email,
                        availability: :online, mfa_method: :disabled,
                        confirmed_at: Time.current, type: 'User')
    UserRole.assign_role_to_user(user, Role.find_by!(key: 'super_admin'))
  end
end
