# frozen_string_literal: true
# The CRM master schema includes Auth tables. This is run only after a schema
# load into an empty database, before either web service starts.
raise 'Auth migration stamp requires an empty user table' if User.exists?

Dir[Rails.root.join('db', 'migrate', '*.rb')].sort.each do |file|
  version = File.basename(file).split('_').first
  ActiveRecord::Base.connection.schema_migration.create_version(version)
rescue ActiveRecord::RecordNotUnique
  nil
end
