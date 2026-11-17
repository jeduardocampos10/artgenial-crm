# This script stamps the Auth migrations that are already present in the
# existing shared database schema before evo-auth runs its normal migration
# command. It only operates on a brand-new installation: if the public.users
# table already has data, then this is an existing installation and the Auth
# migrations must be allowed to run normally.
#
# Auth migrations already represented by that schema. On resume/redeploy with
# Auth data, it leaves any new migration unstamped so the normal db:migrate step
# can apply upgrades instead of skipping them.
connection = ActiveRecord::Base.connection
unless connection.select_value("SELECT to_regclass('public.users')")
  puts 'Auth migration stamp skipped: Auth tables are absent; db:migrate will create them'
  exit
end

if User.exists?
  puts 'Auth migration stamp skipped for existing installation'
  exit
end

versions = Dir[Rails.root.join('db', 'migrate', '*.rb')].sort.map do |file|
  File.basename(file).split('_').first
end
schema_migration = ActiveRecord::SchemaMigration.new(connection)

versions.each do |version|
  schema_migration.create_version(version)
rescue ActiveRecord::RecordNotUnique
  # A concurrent or resumed run inserted the same version. That is safe.
end

puts "Stamped #{versions.length} Auth migration version(s)"
