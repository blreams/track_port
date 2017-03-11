#!/usr/bin/perl -T
# Copyright 2009 BLR.
# All rights reserved.
# This is unpublished, confidential BLR proprietary
# information.  Do not reproduce without written permission.
#
# file:         port_track.cgi
#
# description:
#
# Modification History
#
# when      ver   who       what
# --------  ---   --------  -----------------------------------------
# 01/20/09  1.0   blreams   initial
# 02/12/09  1.1   blreams   pulls port info from DB.
# 02/13/09  1.2   blreams   call pull_transaction_report.cgi with new style parameters.
# 04/17/09  1.3   blreams   added showname parameter selector.
# 08/09/09  1.4   blreams   added showsector parameter selector.
# 08/10/09  1.4a  blreams   no default selection of ports.
# --------  ---   --------  -----------------------------------------
#-----------------------------------------------------------------------------
# Miscellaneous initialization
#-----------------------------------------------------------------------------
use strict;
#use warnings;
use Readonly;
use CGI;
use DBI;

our $script_name = $0; ($0 =~ /\//) && ($0 =~ /\/([^\/\s]*)\s*$/) && ($script_name = $1);
our $script_ver = '1.4a';
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
our $dbh = DBI->connect('dbi:mysql:track_port', 'blreams') or die "ERROR: Connection error: $DBI::errstr\n";
our $q = new CGI;

##############################################################################
# get_all_ports
#   Build query to get all portnames in the port_param table.
#
#   Lone argument is a pointer to a hash of lists.  The hash is indexed on
#   filename and each hash entry contains a list of port names for that file.
#
sub get_all_ports {
  my ($p_hlp) = @_;

  my $query = "SELECT fileportname FROM port_param WHERE (!(fileportname REGEXP '_combined')) ORDER BY portnum";
  my $sth;
  my @dbrow;
  my $f;
  my $p;

  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";

  while (@dbrow = $sth->fetchrow_array()) {
    ($f, $p) = split(/:/, $dbrow[0]);
    $p_hlp->{$f}[scalar(@{$p_hlp->{$f}})] = $p;
  }
}

##############################################################################
# get_tr_fields
#   Build query to get fields for transaction_report table.
#
#   Lone argument is a pointer to a list.  Field names are returned to that
#   list.
#
sub get_tr_fields {
  my ($p_lf) = @_;

  my $query = "DESCRIBE transaction_report";
  my $sth;
  my @dbrow;
  my $f;

  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";

  $f = 0;
  while (@dbrow = $sth->fetchrow_array()) {
    if ($f < 4) { $f++; next; }
    if (($dbrow[0] eq 'symbol') || ($dbrow[0] eq 'label') || ($dbrow[0] eq 'pe')) {
      $dbrow[0] = '_' . $dbrow[0];
    }
    push(@{$p_lf}, $dbrow[0]);
  }
}

#============================================================================
#================ MAIN PROGRAM ==============================================
#============================================================================
our $filename;
our %hash_list_ports;
our @list_sort_fields;
our $p;
our $f;

get_all_ports(\%hash_list_ports);
get_tr_fields(\@list_sort_fields);

print $q->header( 'text/html' );

printf(qq(<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"\n));
printf(qq("http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n));
printf(qq(<html>\n));
printf(qq(  <head>\n));
printf(qq(    <title>Port Track Selection</title>\n));
printf(qq(    <link rel="stylesheet" type="text/css" href="/css/track_port.css" />\n));
printf(qq(  </head>\n));
printf(qq(  <body background="/pics/brickwall.gif" bgcolor="#ffffff">\n));
printf(qq(    <form name="pt_select" action="/cgi-bin/pull_transaction_report.cgi" method="get">\n));
printf(qq(      <table border="1">\n));
printf(qq(        <tr>\n));
$f = 0;
foreach $filename (keys(%hash_list_ports)) {
  if ($f == 10) {
    printf(qq(        </tr>\n));
    printf(qq(        <tr>\n));
    $f = 0;
  }
  printf(qq(          <td valign="top">%s:<br />\n), $filename);
  printf(qq(            <select style="background:WhiteSmoke" name="%s" multiple="multiple" size="20">\n), $filename);
# if ($filename eq 'port') {
#   printf(qq(              <option selected="selected">_ALL_</option>\n));
# } else {
    printf(qq(              <option>_ALL_</option>\n));
# }
  for ($p = 0; $p <= $#{$hash_list_ports{$filename}}; $p++) {
    printf(qq(              <option>%s</option>\n), $hash_list_ports{$filename}[$p]);
  }
  printf(qq(            </select>\n));
  printf(qq(          </td>\n));
  $f++;
}
printf(qq(        </tr>\n));
printf(qq(      </table>\n));
printf(qq(      <table border="1">\n));
printf(qq(        <tr>\n));
printf(qq(          <td valign="top">Method:<br />\n));
printf(qq(            <input type="radio" name="method" value="none" />None<br />\n));
printf(qq(            <input type="radio" name="method" value="diff" checked="checked" />Diff<br />\n));
printf(qq(            <input type="radio" name="method" value="sum" />Sum<br />\n));
printf(qq(          </td>\n));
printf(qq(          <td valign="top">Combined:<br />\n));
printf(qq(            <input type="radio" name="combined" value="TRUE" checked="checked" />TRUE<br />\n));
printf(qq(            <input type="radio" name="combined" value="FALSE" />FALSE<br />\n));
printf(qq(          </td>\n));
printf(qq(          <td valign="top">Show Name:<br />\n));
printf(qq(            <input type="radio" name="showname" value="TRUE" checked="checked" />TRUE<br />\n));
printf(qq(            <input type="radio" name="showname" value="FALSE" />FALSE<br />\n));
printf(qq(          </td>\n));
printf(qq(          <td valign="top">Show Sector:<br />\n));
printf(qq(            <input type="radio" name="showsector" value="TRUE" />TRUE<br />\n));
printf(qq(            <input type="radio" name="showsector" value="FALSE" checked="checked" />FALSE<br />\n));
printf(qq(          </td>\n));
printf(qq(          <td valign="top">Sort:<br />\n));
printf(qq(            <select style="background:WhiteSmoke" name="sort">\n));
foreach $f (@list_sort_fields) {
  if ($f eq 'pct_chg') {
    printf(qq(              <option selected="selected">%s</option>\n), $f);
  } else {
    printf(qq(              <option>%s</option>\n), $f);
  }
}
printf(qq(            </select>\n));
printf(qq(          </td>\n));
printf(qq(        </tr>\n));
printf(qq(      </table>\n));
printf(qq(      <input type="submit" value="Submit" />\n));
printf(qq(      <input type="reset" value="Reset" />\n));
printf(qq(    </form>\n));
printf(qq(  </body>\n));
printf(qq(</html>\n));


