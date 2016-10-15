drop table if exists applications;

create table applications (
  id integer primary key autoincrement,
  firstname varchar(50) not null,
  lastname varchar(50) not null,
  email varchar(100) not null,
  cell_number varchar(20) not null,
  city varchar(50) not null
);
