#!/usr/bin/perl -T
# Copyright 2007 Intel Corporation.
# All rights reserved.
# This is unpublished, confidential Intel proprietary
# information.  Do not reproduce without written permission.
#
# file:         port_chart.cgi
#
# description:
#
# Modification History
#
# when      ver   who       what
# --------  ---   --------  -----------------------------------------
# 03/16/09  1.0   blreams   initial
# 03/24/09  1.0a  blreams   added back and home links.
# 03/24/09  1.0b  blreams   lots of cleanup, generate_chart sub replaced inline code.
# 03/25/09  1.0c  blreams   added nav for fixed time ranges.
# 03/26/09  1.0d  blreams   no level lines above 5 ports, minor cleanup.
# 07/24/09  1.0e  blreams   removed non-one multiplier code.
# 08/06/09  1.0f  blreams   check actual date range instead of number of entries in array.
# 08/06/09  1.0g  blreams   added abovemin and belowmax columns to summary table.
# 08/06/09  1.0h  blreams   added YTD period.
# 08/17/09  1.0i  blreams   fixed bugs w/ YTD calcs.
# 08/26/09  1.0j  blreams   fixed bug in loop that creates %hash_date_index because of quirk in parse_date.
# 08/26/09  1.0k  blreams   added zero_basis support, all pcts are forced to be 0%.
# 01/24/10  1.0l  blreams   added protection for calls when plot parameter is undefined.
# 01/25/10  1.1a  blreams   fixed div0 error on calculating pct_rng when max = min.
# 08/02/10  1.2   blreams   added metadata tag so iphone will not auto link numbers.
# 10/22/10  1.2a  blreams   fixed ytd port_chart cmd to use 12/31/<last_year>.
# 12/26/10  1.3   blreams   added chart resizing and date modification form.
# 12/26/10  1.3a  blreams   put form code in a sub, added custom graph size.
# 01/23/14  1.4   blreams   dynamic width of x-axis tick marks.
# 01/23/14  1.5   blreams   changed font and font sizes for various graph elements.
# --------  ---   --------  -----------------------------------------
#-----------------------------------------------------------------------------
# Miscellaneous initialization
#-----------------------------------------------------------------------------
use strict;
use warnings;
use CGI;
use CGI::Carp qw( fatalsToBrowser );
use DBI;
use Readonly;
use Time::CTime;
use Time::ParseDate;
use GD::Graph::lines;
use GD::Graph::bars;
use GD::Graph::colour;
use IO::File;
use File::Basename;
use Chart::Math::Axis;

#-----------------------------------------------------------------------------
# Assign constants
#-----------------------------------------------------------------------------
our $FALSE = 0;
our $TRUE = 1;
our $secsperday = 60 * 60 * 24;

our $script_name = $0; ($0 =~ /\//) && ($0 =~ /\/([^\/\s]*)\s*$/) && ($script_name = $1);
our $script_ver = '1.5';
our $min_args = 0;
our $max_args = 2;

our $junk;

our %period_days;
our %period_hdrs;
our @periods;

#-----------------------------------------------------------------------------
# Check for correct number of arguments
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

our $q = new CGI;
#$q->param(plot => '');
if ($flag_debug) {
  $q->param(serp  => ('blink', 'serp'));
  $q->param(method => 'sum');
# $q->param(start => '12/15/2011');
# $q->param(end   => '12/19/2011');
}

#########################################################################################
### The following are consided "global" variables in that they are declared here      ###
### before any of the subroutines...meaning they are part of the visible scope        ###
### of these subroutines.  The idea is keep from having to pass every little          ###
### argument.                                                                         ###
#########################################################################################
our $dbh;                            # DB handle, once connected.
our %hash_list_ports;                # Hash of lists, hash index is filename, list of ports in that file.
our %hash_hash_ports;                # Hash of hashes, hash index is filename, hash index is portname.  Used to verify if parameter exists in DB.
our @fileportnames_param;            # List of fileportnames to be plotted, untainted input parameter.
our $method_param;                   # Method, untainted input parameter.
# TODO Need to choose dynamic defaults for start and end parameters.
our $start_param = '';               # Start value for plot, untainted input parameter.
our $end_param = '';                 # End value for plot, untainted input parameter.
our $plot_param = '';                # Indicator plot and type of plot.
our $geom_param = '';                # Geometry of generated charts.
our $cgeom_param = '';               # Custom geometry of generated charts.
our $graph_width = 1400;             # Width of generated charts.
our $graph_height =1050;             # Height of generated charts.
our $graph_title = '';               # String used for titling the chart.
our $start_date;                     # String set to the oldest date in returned dataset.
our $end_date;                       # String set to the newest date in returned dataset.

#our $font = '/usr/share/fonts/truetype/ttf-mgopen/MgOpenModernaRegular.ttf';
our $font = '/usr/share/fonts/truetype/freefont/FreeSans.ttf';

GD::Graph::colour::read_rgb("/etc/X11/rgb.txt");
GD::Graph::colour::add_colour(graph_background => [ 48,  48,  48]);
our @colors = (
# Blue              Purple          Red          Green             Brown
  'MediumBlue',     'DarkOrchid4',  'DarkRed',   'DarkGreen',      'SaddleBrown',
  'MidnightBlue',   'maroon4',      'firebrick', 'SpringGreen4',   'goldenrod4',
  'DeepSkyBlue4',   'VioletRed',    'coral3',    'ForestGreen',    'chocolate',
  'DodgerBlue',     'MediumOrchid', 'tomato',    'MediumSeaGreen', 'DarkOrange2',
  'MidnightBlue',   'DarkOrchid4',  'DarkRed',   'DarkGreen',      'SaddleBrown',
  'MediumBlue',     'maroon4',      'firebrick', 'SpringGreen4',   'goldenrod4',
  'DeepSkyBlue4',   'VioletRed',    'coral3',    'ForestGreen',    'chocolate',
  'DodgerBlue',     'MediumOrchid', 'tomato',    'MediumSeaGreen', 'DarkOrange2',
  'MidnightBlue',   'DarkOrchid4',  'DarkRed',   'DarkGreen',      'SaddleBrown',
  'MediumBlue',     'maroon4',      'firebrick', 'SpringGreen4',   'goldenrod4',
  'DeepSkyBlue4',   'VioletRed',    'coral3',    'ForestGreen',    'chocolate',
  'DodgerBlue',     'MediumOrchid', 'tomato',    'MediumSeaGreen', 'DarkOrange2',
  'MidnightBlue',   'DarkOrchid4',  'DarkRed',   'DarkGreen',      'SaddleBrown',
  'MediumBlue',     'maroon4',      'firebrick', 'SpringGreen4',   'goldenrod4',
  'DeepSkyBlue4',   'VioletRed',    'coral3',    'ForestGreen',    'chocolate',
  'DodgerBlue',     'MediumOrchid', 'tomato',    'MediumSeaGreen', 'DarkOrange2',
);


#########################################################################################
# db_date_to_in_date
#   Converts YYYY-MM-DD dates to mm/dd/yyyy format
sub db_date_to_in_date {
  my ($db_date) = @_;
  return(strftime("%m/%d/%Y", localtime(parsedate($db_date))));
}

#########################################################################################
# setup_periods
#   Sets up the periods used for calculating returns.
#
#   Inputs
#     $edate -- End date used for all relative dates.
sub setup_periods {
  my ($edate) = @_;
  
  my $ytd_days;
  my $ytd_inserted = $FALSE;
  my $period;
  my $last_year;

  ### First step is to figure out how many days from YTD.
  $last_year = strftime("%Y", localtime(parsedate($edate))) - 1;
  #$ytd_days = int(0.5 + ((parsedate($edate) - parsedate("Jan 1 " . substr($edate, 0, 4))) / $secsperday)) - 1;
  $ytd_days = int(0.5 + ((parsedate($edate) - parsedate("Dec 31 $last_year")) / $secsperday)) - 1;

  ### Now build %period_days, %period_hdrs
  %period_days = (
    'year'       => 364,
    'sixmonth'   => 182,
    'quarter'    => 91,
    'month'      => 30,
    'week'       => 7,
    'day'        => 1,
    'ytd'        => $ytd_days,
  );
  %period_hdrs = (
    'year'       => '1y',
    'sixmonth'   => '6m',
    'quarter'    => '3m',
    'month'      => '30d',
    'week'       => '5d',
    'day'        => '1d',
    'ytd'        => 'ytd',
  );

  ### Now build @periods with the correct order.
  @periods = ();
  push(@periods, 'year');
  foreach $period ('sixmonth', 'quarter', 'month', 'week', 'day') {
    if ((! $ytd_inserted) && ($period_days{'ytd'} > $period_days{$period})) {
      push(@periods, 'ytd');
      $ytd_inserted = $TRUE;
    }
    push(@periods, $period);
  }
}

#########################################################################################
# color2hex
#   Translates color name to RGB hex string.
sub color2hex {
  my ($color) = @_;
  my $rv = GD::Graph::colour::rgb2hex(GD::Graph::colour::_rgb($color));
  return($rv);
}

##############################################################################
# get_all_ports
#   Build query to get all portnames in the port_param table.
#
#   Lone argument is a pointer to a hash of lists.  The hash is indexed on
#   filename and each hash entry contains a list of port names for that file.
#
sub get_all_ports {
  my ($p_hlp, $p_hhp) = @_;

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
    $p_hhp->{$f}{$p} = $TRUE;
  }
}

#########################################################################################
# untaint_params
#   untaint $q->param and return each parameter.
#   
#   No outputs, use globals
#     $fileportnames_param
#     $method_param
#     $start_param
#     $end_param
#
sub untaint_params {
  my ($method)   = $q->param('method') =~ /^(diff|sum|none)$/;
  my ($start)    = ($q->param('start'))?($q->param('start') =~ /^(\d\d?\/\d\d?\/\d\d\d\d)$/):$FALSE;
  my ($end)      = ($q->param('end'))?  ($q->param('end')   =~ /^(\d\d?\/\d\d?\/\d\d\d\d)$/):$FALSE;
  my ($plot)     = ($q->param('plot'))? ($q->param('plot')  =~ /^(totals|pcts|sumdiffs)$/): $FALSE;
  my ($geom)     = ($q->param( 'geom'))?($q->param( 'geom') =~ /^(\d\d\d+x\d\d\d+)$/):      '';
  my ($cgeom)    = ($q->param('cgeom'))?($q->param('cgeom') =~ /^(\d\d\d+x\d\d\d+)$/):      '';
  my @ports;
  my @fileportnames;
  # BLR: 07/24/2009 -- Remove non-one multiplier code.
  #my @sorted_fpns;
  my $f;
  my $p;
  my $k;

  foreach $f (keys %hash_list_ports) {
    @ports = $q->param($f);
    foreach $p (@ports) {
      if (! ($p =~ /^([-\w_]+)$/)) { next; }
      if ($p eq '_ALL_') {
        foreach $p (@{$hash_list_ports{$f}}) {
          push(@fileportnames, sprintf("%s:%s", $f, $p));
        }
        last;
      } elsif ($hash_hash_ports{$f}{$p}) {
        push(@fileportnames, sprintf("%s:%s", $f, $p));
      } else {
        printf(STDERR "untaint_params: Bad parameter <%s=%s>\n", $f, $p);
        exit(1);
      }
    }
  }

  if ($method)                { $method_param = $method; }
  if ($start)                 { $start_param = $start; }
  if ($end)                   { $end_param = $end; }
  if ($geom)                  { $geom_param = $geom; }
  if ($cgeom)                 { $cgeom_param = $geom; }
  else                        { $cgeom_param = sprintf("%dx%d", $graph_width, $graph_height); }
  if ($plot)                  { $plot_param = $plot; }
  if (scalar(@fileportnames)) { @fileportnames_param = @fileportnames; }

}

###################################################################################
# get_rel_date
# Gets the relative date that is $days prior to $end_date.
# 
# Input
#   o $edate -- date from which to calculate relative date.
#   o $days -- number of days to go back to calculate return date.
#   o $fmt -- 1->MM/DD/YYYY, 2->YYYY-MM-DD
#
sub get_rel_date {
  my ($edate, $days, $fmt) = @_;
  my $secs = parsedate($edate) - ($days * $secsperday);
  if ($fmt == 1) {
    return(strftime("%m/%d/%Y", localtime($secs)));
  } else {
    return(strftime("%Y-%m-%d", localtime($secs)));
  }
}

###################################################################################
# get_valid_date
# Gets the earliest (or latest) valid date for the targeted fileportnames.
#
# Input:
#   o $which -- 'start' or 'end'.
#   o $p_fpns -- pointer to array of targeted fileportnames.
#
# Returns the requested date in MM/DD/YYYY format.
sub get_valid_date {
  my ($which, $p_fpns) = @_;
  my $potentialsecs;
  my $maxmin;
  my $fpn;
  my $query;
  my $p_db_dates;
  my $datesecs;

  if ($which eq 'start') {
    $potentialsecs = parsedate('01/01/1990');
    $maxmin = 'MIN';
  } elsif ($which eq 'end') {
    $potentialsecs = parsedate('now');
    $maxmin = 'MAX';
  }
  foreach $fpn (@{$p_fpns}) {
    $query = sprintf(qq/SELECT %s(date) AS d FROM port_history WHERE (fileportname = '%s')/, $maxmin, $fpn);
    $p_db_dates = $dbh->selectcol_arrayref($query);
    $datesecs = parsedate($p_db_dates->[0]);
    if ($which eq 'start') {
      if ($datesecs > $potentialsecs) { $potentialsecs = $datesecs; }
    } elsif ($which eq 'end') {
      if ($datesecs < $potentialsecs) { $potentialsecs = $datesecs; }
    }
  }
  return(strftime("%m/%d/%Y", localtime($potentialsecs)));
}

###################################################################################
# build_cgi_cmd
#
# Used to build the same cgi command but allows some of the parameters to be 
# substituted.
#
# Inputs
#   o method -- method parameter, if 0 then method_param
#   o start  -- start parameter, if 0 then start_param
#   o end    -- end parameter, if 0 then end_param
#   o plot   -- plot parameter, if 0 then don't add plot parameter.
sub build_cgi_cmd {
  my ($method, $start, $end, $plot) = @_;
  my ($i, $c, $f, $p);
  my $cgi_cmd = $script_name;

  if (! $method) { $method = $method_param; }
  if (! $start)  { $start  = $start_param; }
  if (! $end)    { $end    = $end_param; }
  for ($i = 0; $i <= $#fileportnames_param; $i++) {
    ($f, $p) = split(/:/, $fileportnames_param[$i]);
    if ($i == 0) { $c = '?'; } else { $c = '&amp;'; }
    $cgi_cmd .= sprintf("%s%s=%s", $c, $f, $p);
  }
  $cgi_cmd .= "&amp;method=$method";
  $cgi_cmd .= "&amp;start=$start";
  $cgi_cmd .= "&amp;end=$end";
  if ($plot) { $cgi_cmd .= "&amp;plot=$plot"; }
  return($cgi_cmd);
}

###################################################################################
# html_header
#
sub html_header {
  printf(qq(<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n));
  printf(qq(<html>\n));
  printf(qq(<head>\n));
  printf(qq(  <meta http-equiv="content-type" content="text/html;charset=iso-8859-1"/>\n));
  printf(qq(  <meta name="generator" content="BLR Tool"/>\n));
  printf(qq(  <meta name="format-detection" content="telephone=no"/>\n));
  printf(qq(  <link rel="stylesheet" type="text/css" href="/css/track_port.css" />\n));
  printf(qq(  <title>%s v%s</title>\n), $script_name, $script_ver);
  printf(qq(  <script type="text/javascript">\n));
  printf(qq(    function ChangeColor(tableRow, highLight, outLight) {\n));
  printf(qq(      if (highLight) {\n));
  printf(qq(        tableRow.style.backgroundColor = '#6666ff';\n));
  printf(qq(      } else {\n));
  printf(qq(        tableRow.style.backgroundColor = outLight;\n));
  printf(qq(      }\n));
  printf(qq(    }\n));
  printf(qq(    function DoNav(theUrl) {\n));
  printf(qq(      document.location.href = theUrl;\n));
  printf(qq(    }\n));
  printf(qq(  </script>\n));
  printf(qq(</head>\n));
  printf(qq(<body background="../../pics/brickwall.gif" bgcolor="#ffffff">\n));
  printf(qq(\n));
}

###################################################################################
# html_form
#
sub html_form {
  my $i;
  my $f;
  my $p;
  my $graph_size = 'Custom';

  if    ($geom_param eq '1920x1080') { $graph_size = 'Large'; }
  elsif ($geom_param eq '1400x1050') { $graph_size = 'Medium'; }
  elsif ($geom_param eq '1024x768')  { $graph_size = 'Small'; }

  printf(qq(<form name="dates_select" action="/cgi-bin/port_chart.cgi" method="get">\n));
  for ($i = 0; $i <= $#fileportnames_param; $i++) {
    ($f, $p) = split(/:/, $fileportnames_param[$i]);
    printf(qq(  <input type="hidden" name="%s" value="%s"/>\n), $f, $p);
  }
  printf(qq(  <input type="hidden" name="method" value="%s"/>\n), $method_param);
  printf(qq(  <table>\n));
  printf(qq(    <tr>\n));
  printf(qq(      <td>\n));
  printf(qq(        <table>\n));
  printf(qq(          <tr><td><input type="submit" value="Submit"/></td></tr>\n));
  printf(qq(        </table>\n));
  printf(qq(      </td>\n));
  printf(qq(      <td>\n));
  printf(qq(        <table>\n));
  printf(qq(          <tr><td>Starting Date:</td></tr>\n));
  printf(qq(          <tr><td><input type="text" name="start" value="%s"/></td></tr>\n), db_date_to_in_date($start_date));
  printf(qq(        </table>\n));
  printf(qq(      </td>\n));
  printf(qq(      <td>\n));
  printf(qq(        <table>\n));
  printf(qq(          <tr><td>Ending Date:</td></tr>\n));
  printf(qq(          <tr><td><input type="text" name="end" value="%s"/></td></tr>\n), db_date_to_in_date($end_date));
  printf(qq(        </table>\n));
  printf(qq(      </td>\n));
  printf(qq(      <td>\n));
  printf(qq(        <table>\n));
  printf(qq(          <tr><td>Graph Size:</td></tr>\n));
  printf(qq(          <tr>\n));
  printf(qq(            <td><input type="radio" name="geom" value="1920x1080"%s/>Large</td>\n), ($graph_size eq 'Large' ? ' checked="checked"' : ''));
  printf(qq(            <td><input type="radio" name="geom" value="1400x1050"%s/>Medium</td>\n), ($graph_size eq 'Medium' ? ' checked="checked"' : ''));
  printf(qq(            <td><input type="radio" name="geom" value="1024x768"%s/>Small</td>\n), ($graph_size eq 'Small' ? ' checked="checked"' : ''));
  printf(qq(            <td><input type="radio" name="geom" value=""%s/>Custom</td>\n), ($graph_size eq 'Custom' ? ' checked="checked"' : ''));
  printf(qq(            <td><input type="text" name="cgeom" value="%s"/></td>\n), $cgeom_param);
  printf(qq(          </tr>\n));
  printf(qq(        </table>\n));
  printf(qq(      </td>\n));
  printf(qq(    </tr>\n));
  printf(qq(  </table>\n));
  printf(qq(</form>\n));
}

###################################################################################
# html_nav
#   Build a string for inclusion in <td> with onmouseover, onmouseout and onclick.
# Inputs
#   o $days -- number of days to go back for new start in cgi cmd.
#   o $bgc -- background color.
#
sub html_nav {
  my ($edate, $days, $bgc) = @_;
  my $rv = '';
  $rv = sprintf(qq(onmouseover="ChangeColor\(this,true,'%s'\);" onmouseout="ChangeColor\(this,false,'%s'\);" onclick="DoNav\('%s'\);"), $bgc, $bgc, build_cgi_cmd(0,get_rel_date($edate, $days, 1),0,0));
}

###################################################################################
# html_table
#
sub html_table {
  my ($r_hash, $edate) = @_;
  my $histtag;
  my $pct_rng;
  my ($H, $M, $L);
  my $i = 0;
  my $period;
  printf(qq(<table border="0" cellpadding="0" cellspacing="0">\n));
  printf(qq(  <tr><td>\n));
  printf(qq(    <table>\n));
  printf(qq(      <tr><td><a href="http://giskard.homelinux.net">HOME</a></td></tr>\n));
  printf(qq(    </table>\n));
  printf(qq(  </td><td>\n));
  printf(qq(    <table class="sum_tab">\n));
  printf(qq(      <tr class="heading">\n));
  printf(qq(        <th>Port</th>\n));
  printf(qq(        <th>Current</th>\n));
  foreach $period (reverse(@periods)) {
    if ($period eq 'day') {
      printf(qq(        <th>%sChg</th>\n), $period_hdrs{$period});
      printf(qq(        <th>%sChg</th>\n), $period_hdrs{$period});
    } else {
      printf(qq(        <th %s>%sChg</th>\n), html_nav($edate, $period_days{$period}, '#A8A8A8'), $period_hdrs{$period});
      printf(qq(        <th %s>%sPct</th>\n), html_nav($edate, $period_days{$period}, '#A8A8A8'), $period_hdrs{$period});
    }
  }
  printf(qq(        <th>Max</th>\n));
  printf(qq(        <th>Min</th>\n));
  printf(qq(        <th>Curr%%Rng</th>\n));
  printf(qq(        <th>%%Above Min</th>\n));
  printf(qq(        <th>%%Below Max</th>\n));
  printf(qq(      </tr>\n));

  foreach $histtag (@fileportnames_param) {
    $H = $r_hash->{$histtag}{'total'}{'max'};
    $M = $r_hash->{$histtag}{'total'}{'last'};
    $L = $r_hash->{$histtag}{'total'}{'min'};
    if ($L < 1) { $L = 1.0; }
    if (($H - $L) < 0.01) {
      $pct_rng    = 0.0;
    } else {
      $pct_rng    = (($M - $L) / ($H - $L)) * 100.0;
    }
    printf(qq(      <tr class="body" bgcolor="%s">\n), color2hex($r_hash->{$histtag}{'color'}));
    printf(qq(        <td class="left">%s</td>\n), $histtag);
    printf(qq(        <td class="right">%.2f</td>\n), $r_hash->{$histtag}{'total'}{'last'});

    foreach $period (reverse(@periods)) {
      printf(qq(        <td class="right">%.2f</td>\n), $r_hash->{$histtag}{'total'}{$period . 'change'});
      printf(qq(        <td class="right">%.2f%%</td>\n), $r_hash->{$histtag}{'total'}{$period . 'pct'});
    }

    printf(qq(        <td class="right">%.2f</td>\n), $r_hash->{$histtag}{'total'}{'max'});
    printf(qq(        <td class="right">%.2f</td>\n), $r_hash->{$histtag}{'total'}{'min'});
    printf(qq(        <td class="right">%.2f%%</td>\n), $pct_rng);
    printf(qq(        <td class="right">%.2f%%</td>\n), (100.0 * (($r_hash->{$histtag}{'total'}{'last'} / $r_hash->{$histtag}{'total'}{'min'}) - 1.0)));
    printf(qq(        <td class="right">%.2f%%</td>\n), (100.0 * (1.0 - ($r_hash->{$histtag}{'total'}{'last'} / $r_hash->{$histtag}{'total'}{'max'}))));
    printf(qq(      </tr>\n));
  }
  if ($method_param eq 'diff') {
    printf(qq(      <tr class="body" bgcolor="%s">\n), color2hex('grey20'));
    printf(qq(        <td class="left">%s</td>\n), 'Diffs');
    printf(qq(        <td class="right">%.2f</td>\n), ($r_hash->{$fileportnames_param[0]}{'total'}{'last'} - $r_hash->{$fileportnames_param[1]}{'total'}{'last'}));
    foreach $period (reverse(@periods)) {
      printf(qq(        <td class="right">%.2f</td>\n), ($r_hash->{$fileportnames_param[0]}{'total'}{$period . 'change'} - $r_hash->{$fileportnames_param[1]}{'total'}{$period . 'change'}));
      printf(qq(        <td class="right"> </td>\n));
    }
    printf(qq(        <td class="right">%.2f</td>\n), ($r_hash->{$fileportnames_param[0]}{'total'}{'max'} - $r_hash->{$fileportnames_param[1]}{'total'}{'max'}));
    printf(qq(        <td class="right">%.2f</td>\n), ($r_hash->{$fileportnames_param[0]}{'total'}{'min'} - $r_hash->{$fileportnames_param[1]}{'total'}{'min'}));
    printf(qq(        <td class="right"> </td>\n));
    printf(qq(        <td class="right"> </td>\n));
    printf(qq(        <td class="right"> </td>\n));
    printf(qq(      </tr>\n));
  }
  printf(qq(    </table>\n));
  printf(qq(  </td></tr>\n));
  printf(qq(</table>\n));
  printf(qq(\n));
}

###################################################################################
# html_body
#
sub html_body {
  my ($plot, $gw, $gh) = @_;
  printf(qq(  <tr><td><img width="%d" height="%d" src="%s" alt=""/></td></tr>\n), $gw, $gh, build_cgi_cmd(0, 0, 0, $plot));
}

###################################################################################
# html_footer
#
sub html_footer {
  printf(qq(\n));
  printf(qq(</body>\n));
  printf(qq(</html>\n));
}

###################################################################################
# generate_chart
#
# Six inputs
#   o $title -- Title for chart
#   o $p_colors -- Pointer to list of colors
#   o $p_linetypes -- Pointer to list of line types
#   o $p_data -- Pointer to chart data array
#   o $axis -- Pointer to Chart::Math::Axis object
#   o $y_num_fmt -- Y-axis number format specifier
sub generate_chart {
  my ($title, $p_colors, $p_linetypes, $p_data, $axis, $y_num_fmt) = @_;
  my $num_data_points = scalar($#{$p_data->[0]});

  my @list_x_label_skips = (5, 22, 64, 129, 260); # (week, month, quarter, semi, year)
  my $x_label_skip = 260;
  my $pixels_per_div;

  for (my $i = 0; $i <= $#list_x_label_skips; $i++) {
    $pixels_per_div = (($graph_width - 120) / $num_data_points) * $list_x_label_skips[$i];
    if ($pixels_per_div > 60) {
      $x_label_skip = $list_x_label_skips[$i];
      last;
    }
  }

  my ($graph) = new GD::Graph::lines($graph_width, $graph_height);
  $graph->set( title             => $title,
               dclrs             => $p_colors,
               bgclr             => 'grey20',
               fgclr             => 'black',
               boxclr            => 'grey80',
               accentclr         => 'white',
               transparent       => $FALSE,
               labelclr          => 'white',
               axislabelclr      => 'white',
               textclr           => 'white',
               legendclr         => 'white',
               line_types        => $p_linetypes,
               line_type_scale   => 10,
               x_labels_vertical => 1,
               long_ticks        => 1,
               x_ticks           => 1,
               x_label           => 1,
               x_label_skip      => $x_label_skip,
               x_tick_offset     => (scalar($#{$p_data->[0]}) % $x_label_skip),
               y_max_value       => $axis->top,
               y_min_value       => $axis->bottom,
               y_tick_number     => $axis->ticks,
               y_label_skip      => 1,
               y_number_format   => $y_num_fmt,
               line_width        => 2,
             );
  $graph->set_legend(@fileportnames_param);
  $graph->set_title_font($font, 14);
  $graph->set_y_axis_font($font, 12);
  $graph->set_x_axis_font($font, 12);
  $graph->set_legend_font($font, 10);
  print $q->header( 'image/png' );
  my $gd_line = $graph->plot($p_data) || die "ERROR: Unable to plot. <" . $graph->error . ">";
  print $gd_line->png;
}

#####################################################################################
# Non-global declarations
#####################################################################################
our $histtag;
our @colorlist = ();
our @colorlist_pct = ();
our @colorlist1 = ();
our @linetypelist = ();
our @linetypelist_pct = ();
our @linetypelist1 = ();
our %hash_stats;
our $axis_totals;
our $axis_pcts;
our $axis_diffs;
our $fpn;
our $fpns;
our $query;
our $p_db_dates;
our $p_db_totals;
our @data_totals;
our @data_sumdiffs;
our @data_pcts;
our $hindex;
our $row;
our $m;
our $h;
our $i;
our $j;
our %hash_date_index;
our $change_tag;
our $pct_tag;
our $period;
our $last_date;
our $last_index;
our @zero_basis;

### Connect to DB.
$dbh = DBI->connect('dbi:mysql:track_port', 'blreams') or die "ERROR: Connection error: $DBI::errstr\n";

### Build %hash_list_ports from DB.
get_all_ports(\%hash_list_ports, \%hash_hash_ports);

### Untaint and process parameters.
untaint_params;

$m = ($method_param eq 'diff') ? -1.0 : (($method_param eq 'sum') ? 1.0 : 0.0);

our $valid_start = get_valid_date('start', \@fileportnames_param);
if ($start_param) {
  if (parsedate($start_param) < parsedate($valid_start)) { $start_param = $valid_start; }
} else {
  $start_param = $valid_start;
}

our $valid_end = get_valid_date('end', \@fileportnames_param);
if ($end_param) {
  if (parsedate($end_param) > parsedate($valid_end)) { $end_param = $valid_end; }
} else {
  $end_param = $valid_end;
}

our $start_date_db = strftime("%Y-%m-%d", localtime(parsedate($start_param)));
our $end_date_db = strftime("%Y-%m-%d", localtime(parsedate($end_param)));
### Loop over each specified port.
for ($h = 0; $h <= $#fileportnames_param; $h++) {
  $fpn = $fileportnames_param[$h];
  ### TODO Need to validate each ports dates to insure exact match
  $query = sprintf("SELECT date FROM port_history WHERE ((date >= '%s') AND (date <= '%s') and (fileportname = '%s')) ORDER by date", $start_date_db, $end_date_db, $fpn);
  $p_db_dates = $dbh->selectcol_arrayref($query);
  $query = sprintf("SELECT total FROM port_history WHERE ((date >= '%s') AND (date <= '%s') and (fileportname = '%s')) ORDER by date",$start_date_db, $end_date_db, $fpn);
  $p_db_totals = $dbh->selectcol_arrayref($query);
  $data_totals[0] = $p_db_dates;
  $data_totals[$h+1] = $p_db_totals;
  $colorlist[$h] = $colorlist_pct[$h] = $colors[$h];
  $linetypelist[$h] = $linetypelist_pct[$h] = 1;
  if ($h > 0) { 
    $graph_title .= ' vs. ';
  }
  $graph_title .= $fileportnames_param[$h];
}

$data_pcts[0] = $p_db_dates;
$data_sumdiffs[0] = $p_db_dates;

%hash_date_index = ();
$hash_date_index{$p_db_dates->[0]} = 0;
$last_date = $p_db_dates->[0];
$last_index = 0;
for ($i = 1, $j = 1; $i <= $#{$p_db_dates}; $i++, $j++) {
  ### BLR -- Bug fix, added 3600 seconds to parse_date calculation to insure we get past the day changeover.
  while ($p_db_dates->[$i] ne strftime("%Y-%m-%d", localtime(parsedate($last_date) + $secsperday + 3600))) {
    $last_date = strftime("%Y-%m-%d", localtime(parsedate($last_date) + $secsperday + 3600));
    $hash_date_index{$last_date} = $last_index;
  }
  $hash_date_index{$p_db_dates->[$i]} = $i;
  $last_date = $p_db_dates->[$i];
  $last_index = $i;
}

for ($h = 0; $h <= $#fileportnames_param; $h++) {
  $zero_basis[$h] = $FALSE;
  if ($data_totals[$h+1][0] < 0.5) { $zero_basis[$h] = $TRUE; }
  for ($row = 0; $row <= $#{$data_totals[0]}; $row++) {
    if (! $zero_basis[$h]) {
      $data_pcts[$h+1][$row] = (($data_totals[$h+1][$row] / $data_totals[$h+1][0]) - 1.0) * 100.0;
    } else {
      $data_pcts[$h+1][$row] = 0.0;
    }
    if ($h == 0) {
      $data_sumdiffs[1][$row] = $data_totals[$h+1][$row];
    } else {
      $data_sumdiffs[1][$row] += ($m * $data_totals[$h+1][$row]);
    }
  }

  ### Figure out the latest date in the dataset.
  $end_date = $data_totals[0][$#{$data_totals[0]}];

  ### Use Axis module to get the max and min values for the port just loaded.
  $histtag = $fileportnames_param[$h];
  $hindex = $#{$data_totals[$h+1]};

  setup_periods($end_date);
  foreach $period (@periods) {
    $change_tag = $period . 'change';
    $pct_tag = $period . 'pct';
     
    $hash_stats{$histtag}{'total'}{$change_tag}     = 0.0;
    $hash_stats{$histtag}{'total'}{$pct_tag}        = 0.0;
    if ((! $zero_basis[$h]) && (exists($hash_date_index{get_rel_date($end_date, $period_days{$period}, 2)}))) { 
      $hash_stats{$histtag}{'total'}{$change_tag} = ($data_totals[$h+1][$hindex] - $data_totals[$h+1][$hash_date_index{get_rel_date($end_date, $period_days{$period}, 2)}]);
      $hash_stats{$histtag}{'total'}{$pct_tag}    = 100.0 * $hash_stats{$histtag}{'total'}{$change_tag} / $data_totals[$h+1][$hash_date_index{get_rel_date($end_date, $period_days{$period}, 2)}];
    }
  }

  $axis_totals = Chart::Math::Axis->new();
  $axis_totals->add_data(@{$data_totals[$h+1]});
  $hash_stats{$histtag}{'total'}{'max'} = $axis_totals->max();
  $hash_stats{$histtag}{'total'}{'min'} = $axis_totals->min();
  $hash_stats{$histtag}{'total'}{'last'} = $data_totals[$h+1][$hindex];

  $axis_pcts = Chart::Math::Axis->new();
  $axis_pcts->add_data(@{$data_pcts[$h+1]});
  $hash_stats{$histtag}{'pct'}{'max'} = $axis_pcts->max();
  $hash_stats{$histtag}{'pct'}{'min'} = $axis_pcts->min();

  $hash_stats{$histtag}{'color'} = $colors[$h];
}

if ($plot_param) {
  ### Use Chart::Math::Axis module to do axis scaling.
  $axis_totals = Chart::Math::Axis->new();
  $axis_pcts = Chart::Math::Axis->new();
  for ($h = 1; $h <= $#data_totals; $h++) {
    $axis_totals->add_data(@{$data_totals[$h]});
    $axis_pcts->add_data(@{$data_pcts[$h]});
  }
  
  ### This is strictly for adding level lines to the data array.  In this case because the level line is
  ### a constant value, we only need to store it in the first and last elements.  The GD package will 
  ### connect the two points with a decorated line.
  if (scalar(@fileportnames_param) <= 5) {
    # Once you get beyond about 5 lines, you should not have level lines, too busy.
    for ($h = 0; $h <= $#fileportnames_param; $h++) {
      ### Doctor data_totals array with additional lines.
      $histtag = $fileportnames_param[$h];
      $colorlist[$#colorlist+1] = $colors[$h];
      $colorlist[$#colorlist+1] = $colors[$h];
      $linetypelist[$#linetypelist+1] = 4;
      $linetypelist[$#linetypelist+1] = 4;
      $j = scalar(@data_totals);
      $data_totals[$j][0]                             = $hash_stats{$histtag}{'total'}{'max'};
      $data_totals[$j][scalar($#{$data_totals[0]})]   = $hash_stats{$histtag}{'total'}{'max'};
      $data_totals[$j+1][0]                           = $hash_stats{$histtag}{'total'}{'min'};
      $data_totals[$j+1][scalar($#{$data_totals[0]})] = $hash_stats{$histtag}{'total'}{'min'};
    
      ### Do same for data_pcts array
      $colorlist_pct[$#colorlist_pct+1] = $colors[$h];
      $colorlist_pct[$#colorlist_pct+1] = $colors[$h];
      $linetypelist_pct[$#linetypelist_pct+1] = 4;
      $linetypelist_pct[$#linetypelist_pct+1] = 4;
      $j = scalar(@data_pcts);
      $data_pcts[$j][0]                           = $hash_stats{$histtag}{'pct'}{'max'};
      $data_pcts[$j][scalar($#{$data_pcts[0]})]   = $hash_stats{$histtag}{'pct'}{'max'};
      $data_pcts[$j+1][0]                         = $hash_stats{$histtag}{'pct'}{'min'};
      $data_pcts[$j+1][scalar($#{$data_pcts[0]})] = $hash_stats{$histtag}{'pct'}{'min'};
    }
  }
  
  ### Now add a black line for the zero axis.
  $colorlist_pct[$#colorlist_pct+1] = 'black';
  $linetypelist_pct[$#linetypelist_pct+1] = 1;
  $j = scalar(@data_pcts);
  $data_pcts[$j][0]                           = 0;
  $data_pcts[$j][scalar($#{$data_pcts[0]})]   = 0;
  
  ### Similarly, add level lines to the data_sumdiffs array for diff or sum.
  $axis_diffs = Chart::Math::Axis->new();
  $axis_diffs->add_data(@{$data_sumdiffs[1]});
  if (! ($method_param eq 'none')) {
    $colorlist1[0] = 'Blue';
    if ($method_param eq 'diff') { $colorlist1[0] = 'DarkRed';   }
    if ($method_param eq 'sum')  { $colorlist1[0] = 'DarkGreen'; }
    $colorlist1[1] = 'black'; 
    $colorlist1[2] = 'DarkGreen'; 
    $colorlist1[3] = 'DarkRed';
    $linetypelist1[0] = 1; 
    $linetypelist1[1] = 1; 
    $linetypelist1[2] = 4;
    $linetypelist1[3] = 4;
    $data_sumdiffs[2][0]                             = 0;
    $data_sumdiffs[2][scalar($#{$data_sumdiffs[0]})] = 0;
    $data_sumdiffs[3][0]                             = $axis_diffs->max();
    $data_sumdiffs[3][scalar($#{$data_sumdiffs[0]})] = $axis_diffs->max();
    $data_sumdiffs[4][0]                             = $axis_diffs->min();
    $data_sumdiffs[4][scalar($#{$data_sumdiffs[0]})] = $axis_diffs->min();
  }
}
  
##################################################
### Below here is where we do the actual graphing.
##################################################
if (! $plot_param) {
  $end_date = $data_totals[0][$#{$data_totals[0]}];
  $start_date = $data_totals[0][0];
  if    ($geom_param)  { ($graph_width, $graph_height) = split(/x/, $geom_param); }
  elsif ($cgeom_param) { ($graph_width, $graph_height) = split(/x/, $cgeom_param); }
  else                 { $graph_width = 1400; $graph_height = 1050; }
  ### HTML generation
  print $q->header( 'text/html' );
  html_header;
  html_table(\%hash_stats, $end_date);
  html_form;
  printf(qq(<table>\n));
  html_body('totals', $graph_width, $graph_height);
  html_body('pcts', $graph_width, $graph_height);
  if (! ($method_param eq 'none')) { 
    html_body('sumdiffs', $graph_width, $graph_height);
  }
  printf(qq(</table>\n));
  html_footer;

} else {
  if ($plot_param eq 'totals') { 
    generate_chart($graph_title, \@colorlist, \@linetypelist, \@data_totals, $axis_totals, "\$%.0f"); 
  } elsif ($plot_param eq 'pcts') { 
    generate_chart(sprintf("%s percentage", $graph_title), \@colorlist_pct, \@linetypelist_pct, \@data_pcts, $axis_pcts, "%.1f%%");
  } elsif ($plot_param eq 'sumdiffs') { 
    generate_chart(sprintf("%s %s", $graph_title, (($method_param eq 'diff') ? 'difference' : 'sum')), \@colorlist1, \@linetypelist1, \@data_sumdiffs, $axis_diffs, "\$%.0f"); 
  }
}

