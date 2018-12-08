#!/usr/bin/perl -T
# Copyright 2009 BLR.
# All rights reserved.
# This is unpublished, confidential BLR proprietary
# information.  Do not reproduce without written permission.
#
# file:         backend_stats.cgi
#
# description:
#
# Modification History
#
# when      ver   who       what
# --------  ---   --------  -----------------------------------------
# 06/21/11  1.0   blreams   initial
# 02/19/14  1.1   blreams   changed thresholds for bgcolor in table
# --------  ---   --------  -----------------------------------------
#-----------------------------------------------------------------------------
# Miscellaneous initialization
#-----------------------------------------------------------------------------
use strict;
#use warnings;
use Readonly;
use CGI;
use DBI;
use Time::CTime;
use Time::ParseDate;

our $script_name = $0; ($0 =~ /\//) && ($0 =~ /\/([^\/\s]*)\s*$/) && ($script_name = $1);
our $script_ver = '1.1';
our $min_args = 0;
our $max_args = 2;

sub usage {
  printf(STDERR "\n");
  printf(STDERR "USAGE: $script_name  [--help] [--version] [--debug] [--verbose] \n");
  printf(STDERR "USAGE:   [--help] - help information\n");
  printf(STDERR "USAGE:   [--version] - version information\n");
  printf(STDERR "USAGE:   [--debug] - print debug messages\n");
  printf(STDERR "USAGE:   [--verbose] - print verbose messages\n");
  printf(STDERR "\n");
}

#-----------------------------------------------------------------------------
# Assign constants
#-----------------------------------------------------------------------------
Readonly our $FALSE => 0;
Readonly our $TRUE  => 1;

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
our $flag_debug = $FALSE;
our $arg = '';
while ($#ARGV >= 0) {
  $arg = shift;
  if ($arg eq '--debug') {
    $flag_debug = $TRUE;
    next;
  }
}

our $dbh = DBI->connect('dbi:mysql:track_port', 'blreams') or die "ERROR: Connection error: $DBI::errstr\n";
our $q = new CGI;
if ($flag_debug) {
# $q->param(date_selector => 'yesterday');
}

##############################################################################
### The following are global variables declared here before any subroutines.
##############################################################################
our $date_param = strftime("%Y-%m-%d", localtime(parsedate('today')));

##############################################################################
# untaint_params
#   untaint $q->param and return each parameter.
#
#   No outputs, use globals
#     $date_param
##############################################################################
sub untaint_params {
  my ($date) = strftime("%Y-%m-%d", localtime(parsedate($q->param('date_selector'))));
  if ($date) { $date_param = $date; }
}

##############################################################################
# get_stats
#   Build query to get backend stats for specified date.
#
#   First argument is a pointer to a list containing put_stat row headers.
#   Second argument is a pointer to a list that will contain put_stat row data.
#   Third argument is a DB valid date string.
#
sub get_stats {
  my ($p_lf, $p_ls, $day) = @_;
  #my $today = strftime("%Y-%m-%d", localtime(parsedate('now')));

  my $query = "SELECT * FROM put_stats WHERE (put_date = '$day') ORDER BY put_time";
  my $sth;
  my @dbrow;
  my $i = 0;
  my $f = 0;

  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";

  while (@dbrow = $sth->fetchrow_array()) {
    for ($i = 0; $i <= $#{$p_lf}; $i++) {
      $p_ls->[$f]{$p_lf->[$i]} = $dbrow[$i];
    }
    $f++;
  }
}

##############################################################################
# get_ps_fields
#   Build query to get fields for put_stats table.
#
#   Lone argument is a pointer to a list.  Field names are returned to that
#   list.
#
sub get_ps_fields {
  my ($p_lf) = @_;

  my $query = "DESCRIBE put_stats";
  my $sth;
  my @dbrow;
  my $f;

  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";

  $f = 0;
  while (@dbrow = $sth->fetchrow_array()) {
    push(@{$p_lf}, $dbrow[0]);
  }
}

##############################################################################
# get_valid_dates
#   Build query to get unique put_dates from put_stats table;
#
#   Lone argument is a pointer to a list.  Dates names are returned to that
#   list.
#
sub get_valid_dates {
  my ($p_lvd) = @_;

  my $query = "SELECT DISTINCT put_date FROM put_stats ORDER BY put_date";
  my $sth;
  my @dbrow;
  my $f;

  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";

  $f = 0;
  while (@dbrow = $sth->fetchrow_array()) {
    push(@{$p_lvd}, $dbrow[0]);
  }
}

##############################################################################
# form_table
#   Generate html for form table.
#
#   Lone argument is a pointer to list_valid_dates data.
#
sub form_table {
  my ($p_dates) = @_;
  my $i = 0;

  printf(qq(<form name="date_select" action="/scgi-bin/backend_stats.cgi" method="get">\n));
  printf(qq(<table class="form_tab">\n));
  printf(qq(  <tr>\n));
  printf(qq(    <td><input type="submit" value="Submit"/></td>\n));
  printf(qq(    <td>\n));
  printf(qq(      <select name="date_selector">\n));
  foreach my $d (@{$p_dates}) {
    printf(qq(        <option>%s</option>\n), $d);
  }
  printf(qq(      </select>\n));
  printf(qq(    </td>\n));
  printf(qq(  </tr>\n));
  printf(qq(</table>\n));
}

##############################################################################
# summary_table
#   Generate html for summary table.
#
#   Lone argument is a pointer to put_stats_rows data.
#
sub summary_table {
  my ($p_rows) = @_;
  my $query_seconds;
  my $i = 0;
  my $qt = 0;

  for ($i = 0; $i <= $#{$p_rows}; $i++) {
    $query_seconds = parsedate(($p_rows->[$i]{'query_date'} . ' ' . ($p_rows->[$i]{'query_etime'}))) - parsedate(($p_rows->[$i]{'query_date'} . ' ' . ($p_rows->[$i]{'query_stime'})));
    $qt += $query_seconds;
  }

  if ($#{$p_rows} >= 0) {
  printf(qq(<table class="sum_tab">\n));
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Backend Version', $p_rows->[$#{$p_rows}]{'put_version'});
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Last Backend Put', ($p_rows->[$#{$p_rows}]{'put_date'} . ' ' . $p_rows->[$#{$p_rows}]{'put_time'}));
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Last Query', ($p_rows->[$#{$p_rows}]{'query_date'} . ' ' . ($p_rows->[$#{$p_rows}]{'query_etime'})));
  $query_seconds = parsedate(($p_rows->[$#{$p_rows}]{'query_date'} . ' ' . ($p_rows->[$#{$p_rows}]{'query_etime'}))) - parsedate(($p_rows->[$#{$p_rows}]{'query_date'} . ' ' . ($p_rows->[$#{$p_rows}]{'query_stime'})));
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Last Query Elapsed', $query_seconds);
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Symbols Retrieved', $p_rows->[$#{$p_rows}]{'num_symbols'});
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Symbols In Error', $p_rows->[$#{$p_rows}]{'num_errors'});
  printf(qq(  <tr><td>%s</td><td>%s</td></tr>\n), 'Iterations', (scalar(@{$p_rows})));
  printf(qq(  <tr><td>%s</td><td>%.1f</td></tr>\n), 'Avg Query Time', ($qt/scalar(@{$p_rows})));
  printf(qq(</table>\n));
  }
}

##############################################################################
# data_table
#   Generate html for data table.
#
#   First argument is a pointer to list of DB headers.
#   Second argument is a pointer to put_stats_rows data.
#
sub data_table {
  my ($p_headers, $p_rows) = @_;
  my $query_seconds;
  my $header;
  my $i;
  my @colors = ('#CF8D72', '#EACDC1');
  my $warn_yellow = '#FFE920';
  my $warn_red = '#FF2626';
  my $bgcolor = '';

  printf(qq(<table border="1">\n));

  ### Create the header row
  printf(qq(  <tr>\n));
  foreach $header (@{$p_headers}) {
    printf(qq(    <th>%s</th>\n), $header);
  }
  printf(qq(    <th>%s</th>\n), 'Elapsed Time');
  printf(qq(  </tr>\n));

  ### Create the header row
  for ($i = $#{$p_rows}; $i >= 0; $i--) {
    $query_seconds = parsedate(($p_rows->[$i]{'query_date'} . ' ' . ($p_rows->[$i]{'query_etime'}))) - parsedate(($p_rows->[$i]{'query_date'} . ' ' . ($p_rows->[$i]{'query_stime'})));
    $bgcolor = ($query_seconds > 240) ? $warn_red : (($query_seconds > 120) ? $warn_yellow : $colors[($i % scalar(@colors))]);
    printf(qq(  <tr bgcolor="%s">\n), $bgcolor);
    foreach $header (@{$p_headers}) {
      printf(qq(    <td class="center">%s</td>\n), $p_rows->[$i]{$header});
    }
    printf(qq(    <td class="center">%s</td>\n), $query_seconds);
    printf(qq(  </tr>\n));
  }

  printf(qq(</table>\n));
}

#============================================================================
#================ MAIN PROGRAM ==============================================
#============================================================================
our @list_fields;
our @list_valid_dates;
our @put_stats_rows;

untaint_params;
get_ps_fields(\@list_fields);
get_valid_dates(\@list_valid_dates);
get_stats(\@list_fields, \@put_stats_rows, $date_param);

print $q->header( 'text/html' );
printf(qq(<html>\n));
printf(qq(  <head>\n));
printf(qq(    <title>Backend Statistics</title>\n));
printf(qq(    <link rel="stylesheet" type="text/css" href="/css/track_port.css" />\n));
printf(qq(  </head>\n));
printf(qq(  <body background="/pics/brickwall.gif" bgcolor="#ffffff">\n));
form_table(\@list_valid_dates);
summary_table(\@put_stats_rows);
data_table(\@list_fields, \@put_stats_rows);
printf(qq(  </body>\n));
printf(qq(</html>\n));


