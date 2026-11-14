# frozen_string_literal: true
# The CRM master schema includes Auth tables. On first install this records the
# Auth migrations already represented by that schema. On resume/redeploy with
# Auth data, it leaves any new migration unstamped so the normal db:migrate step
# can apply upgrades instead of skipping them.
if User.exists?
  puts 'Auth migration stamp skipped for existing installation'
  exit
end

versions = Dir[Rails.root.join('db', 'migrate', '*.rb')].sort.map do |file|
  File.basename(file).split('_').first
end
connection = ActiveRecord::Base.connection
schema_migration = ActiveRecord::SchemaMigration.new(connection)

versions.each do |version|
  schema_migration.create_version(version)
rescue ActiveRecord::RecordNotUnique
  nil
end
