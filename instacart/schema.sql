drop table if exists onboarding;
drop table if exists quiz;
drop table if exists applications;

create table applications (
  id integer primary key autoincrement,
  created datetime not null default CURRENT_TIMESTAMP,
  status varchar(1) not null default 'p', /* p=pending, h=hired, r=rejected */
  firstname varchar(50) not null,
  lastname varchar(50) not null,
  email varchar(100) not null,
  cell_number varchar(20) not null,
  city varchar(50) not null
);

create index created_status on applications(created, status);

create table quiz (
  id integer primary key autoincrement,
  application_id integer not null,
  created datetime not null default CURRENT_TIMESTAMP,
  completed datetime default null,
  foreign key(application_id) references application(id)
);

create table onboarding (
  id integer primary key autoincrement,
  application_id integer not null,
  created datetime not null default CURRENT_TIMESTAMP,
  completed datetime default null,
  foreign key(application_id) references application(id)
);
