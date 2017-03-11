#!/usr/bin/perl -T
# Copyright 2007 Intel Corporation.
# All rights reserved.
# This is unpublished, confidential Intel proprietary
# information.  Do not reproduce without written permission.
#
# file:         port_pie.cgi
#
# description:
#
# Modification History
#
# when      ver   who       what
# --------  ---   --------  -----------------------------------------
# 07/27/09  1.0   blreams   initial
# 07/30/09  1.0a  blreams   Infrastructure to generate html page and populate with charts.
# 08/04/09  1.1   blreams   data and chart generation added, first pie charts created.
# 10/19/10  1.1a  blreams   pie data labels don't like multiline.
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
use GD::Graph::pie;
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
our $script_ver = '1.1a';
our $min_args = 0;
our $max_args = 2;

our $junk;

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
if ($flag_debug) {
  $q->param(spp    => ('rsu'));
  $q->param(geom => '640x480');
  $q->param(combined => 'TRUE');
  $q->param(plot => 'positions_cash');
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
our $geom_param = '150x80';          # Geometry, untainted input parameter.
our $combined_param = '';            # Indicator of position combining.
our $plot_param = '';                # Indicator plot and type of plot.
our $graph_title = 'Summary';        # String used for titling the chart.
our %hash_port_param;                # Hash of hashes containing queried port_param data.

our $font = '/usr/share/fonts/truetype/ttf-mgopen/MgOpenModernaRegular.ttf';

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
# color2hex
#   Translates color name to RGB hex string.
sub color2hex {
  my ($color) = @_;
  my $rv = GD::Graph::colour::rgb2hex(GD::Graph::colour::_rgb($color));
  return($rv);
}

#########################################################################################
# calc_bgcolor
#   The idea is to return a background color, green for positive, red for negative
#   with the intensity reflecting the relative percentage.
#     > 10.0        #00f800
#
#        0.1        #e0f8e0
#        0.0        #cccccc
#       -0.1        #f8e0e0
#
#     <-10.0        #f80000
#   Takes three input parameters:
#     $pct   -- Percentage value to use for calculating the returned color
#     $min   -- Min percentage (+/-) which returns neutral/gray color
#     $max   -- Max percentage (+/-) which returns saturated green/red
#   Returns a string representing the RGB color value.
sub calc_bgcolor {
  my ($pct, $min, $max) = @_;
  my ($red, $grn, $blu, $normalizer);

  if    (($pct <= $min) && ($pct >= -$min)) {  $red = 0xcc; $grn = 0xcc; $blu = 0xcc;  }
  elsif ($pct >= $max)                      {  $red = 0x00; $grn = 0xf8; $blu = 0x00;  }
  elsif ($pct <= -$max)                     {  $red = 0xf8; $grn = 0x00; $blu = 0x00;  }
  else {
    if ($pct > 0) {
      $normalizer = $pct / $max;
      $red = 0xe0 - int(0xe0 * $normalizer);
      $grn = 0xff;
      $blu = 0xe0 - int(0xe0 * $normalizer);
    } else {
      $normalizer = $pct / -$max;
      $red = 0xf8;
      $grn = 0xe0 - int(0xe0 * $normalizer);
      $blu = 0xe0 - int(0xe0 * $normalizer);
    }
  }

  return(sprintf("#%02x%02x%02x", $red, $grn, $blu));
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
#
sub untaint_params {
  my ($geom)     = $q->param('geom') =~ /^(\d+x\d+)$/;
  my ($combined) = $q->param('combined') =~ /^(TRUE|FALSE)$/;
  my ($plot)     = $q->param('plot') =~ /^(html|summary|positions_cash|positions_nocash)$/;
  my @ports;
  my @fileportnames;
  my $f;
  my $p;
  my $k;

  if ($geom)                  { $geom_param = $geom; }
  if ($combined)              { $combined_param = (($combined eq 'TRUE') ? 1 : 0); }
  if ($plot)                  { $plot_param = $plot; }

  foreach $f (keys %hash_list_ports) {
    @ports = $q->param($f);
    foreach $p (@ports) {
      if (! ($p =~ /^([-\w_]+)$/)) { next; }
      if ($p eq '_ALL_') {
        foreach $p (@{$hash_list_ports{$f}}) {
          if ($combined_param) { $p .= '_combined'; }
          push(@fileportnames, sprintf("%s:%s", $f, $p));
        }
        last;
      } elsif ($hash_hash_ports{$f}{$p}) {
        if ($combined_param) { $p .= '_combined'; }
        push(@fileportnames, sprintf("%s:%s", $f, $p));
      } else {
        printf(STDERR "untaint_params: Bad parameter <%s=%s>\n", $f, $p);
        exit(1);
      }
    }
  }

  if (scalar(@fileportnames)) { @fileportnames_param = @fileportnames; }
}

###################################################################################
# build_cgi_cmd
#
# Used to build the same cgi command but allows some of the parameters to be 
# substituted.
#
# Inputs
#   o fpn    -- fileportname
#   o plot   -- plot parameter, if 0 then don't add plot parameter.
sub build_cgi_cmd {
  my ($fpn, $plot) = @_;
  my ($i, $f, $p);
  my $cgi_cmd = $script_name;

  ($f, $p) = split(/:/, $fpn);
  if ($combined_param) { $p =~ s/_combined$//; }
  $cgi_cmd .= sprintf("?%s=%s", $f, $p);
  $cgi_cmd .= sprintf("&%s=%s", 'geom', '640x480');
  $cgi_cmd .= sprintf("&%s=%s", 'combined', ($combined_param ? 'TRUE' : 'FALSE'));

  if ($plot) { $cgi_cmd .= "&plot=$plot"; }
  return($cgi_cmd);
}

#########################################################################################
# html_header
#   Create the header for the main html file.  Also
sub html_header {
  printf(qq(<html>\n));
  printf(qq(<head>\n));
  printf(qq(  <meta http-equiv="content-type" content="text/html;charset=iso-8859-1">\n));
  printf(qq(  <meta name="generator" content="BLR Tool">\n));
  printf(qq(  <title>%s v%s</title>\n), $script_name, $script_ver);
  printf(qq(  <link rel="stylesheet" type="text/css" href="/css/track_port.css" />\n));
  printf(qq(  <script type="text/javascript">\n));
  printf(qq(    function ChangeColor(tableRow, highLight, outLight) {\n));
  printf(qq(      if (highLight) {\n));
  printf(qq(        tableRow.style.backgroundColor = '#6666ff';\n));
  printf(qq(      } else {\n));
  printf(qq(        tableRow.style.backgroundColor = outLight;\n));
  printf(qq(      }\n));
  printf(qq(    }\n));
  printf(qq(    function DoNav(theUrl,theName) {\n));
  printf(qq(      //document.location.href = theUrl;\n));
  printf(qq(      window.open(theUrl,theName);\n));
  printf(qq(    }\n));
  printf(qq(  </script>\n));
  printf(qq(</head>\n));
  printf(qq(\n));
  printf(qq(<body background="/pics/brickwall.gif" bgcolor="#ffffff">\n));
}

###################################################################################
# html_body
#
sub html_body {
  my ($fpn, $gw, $gh, $plot) = @_;
  printf(qq(  <td><img width=%d height=%d src="%s"></td>\n), $gw, $gh, build_cgi_cmd($fpn, $plot));
}

###################################################################################
# html_footer
#
sub html_footer {
  printf(qq(</body>\n));
  printf(qq(</html>\n));
}

#########################################################################################
# get_ticker_table
#   Build db query for the ticker table, query the db, fetch rows to build a hash
#   that contains the data.  Use this data to build a ticker html table.
#
#   Returns a string that is the html ticker table.
#
#   No inputs in the argument list (uses globals)
#
sub get_ticker_table {

  my $query;
  my $dbtable;
  my @dbrows;
  my $rv = '';
  my $i = 0;
  my $j = 0;
  my $h;
  my $m;
  my $s;
  my $row;
  my $color_col;
  my $tag;
  my $href;
  my @ticker_rows = (
    {'hdr' => 'Symbol',   'dbcol' => 'finance_quote.symbol', 'fmt' => 0},
    {'hdr' => 'Chg',      'dbcol' => 'net',                  'fmt' => 3},
    {'hdr' => 'Chg%',     'dbcol' => 'p_change',             'fmt' => 2},
    {'hdr' => 'Last',     'dbcol' => 'last',                 'fmt' => 1},
    {'hdr' => 'High',     'dbcol' => 'high',                 'fmt' => 1},
    {'hdr' => 'Low',      'dbcol' => 'low',                  'fmt' => 1},
  );

  ### Build, prepare and execute join query
  $query = 'SELECT ';
  for ($i = 0; $i <= $#ticker_rows; $i++) {
    $row = $ticker_rows[$i];
    $query .= sprintf("%s,", $row->{'dbcol'});
    if ($row->{'dbcol'} eq 'p_change') { $color_col = $i; }
  }
  $query .= 'date,time';
  $query .= ' FROM finance_quote JOIN ticker_symbols ON finance_quote.symbol=ticker_symbols.symbol';
  $dbtable = $dbh->selectall_arrayref($query);

  ### Save quote date and time
  ($h, $m, $s) = split(/:/, $dbtable->[0][$#ticker_rows + 2]);
  if ($h < 5) { $h += 12; }
# $quote_seconds = parsedate($dbtable->[0][$#ticker_rows + 1] . ' ' . sprintf("%02d:%02d:%02d", $h, $m, $s));

  $rv = sprintf(qq(  <TABLE CLASS="tick_tab">\n));
  $rv .= sprintf(qq(    <TR>\n));
  for ($i = 0; $i <= $#ticker_rows; $i++) {
    $rv .= sprintf(qq(<TH>%s</TH>\n), $ticker_rows[$i]{'hdr'});
  }
  $rv .= sprintf(qq(    </TR>\n));
  for ($j = 0; $j < scalar(@{$dbtable}); $j++) {
    $rv .= sprintf(qq(    <TR>\n));
    for ($i = 0; $i <= $#ticker_rows; $i++) {
      $tag = 'TD';
      if ($ticker_rows[$i]{'fmt'} == 0) {
        $href = sprintf(qq(<A HREF="http://finance.yahoo.com/q?s=%s" TARGET= "_blank"><B>%s</B></A>), lc($dbtable->[$j][$i]), $dbtable->[$j][$i]);
        $rv .= sprintf(qq(      <%s BGCOLOR=%s CLASS="left">%s</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $href, $tag);
      } elsif ($ticker_rows[$i]{'fmt'} == 1) {
        $rv .= sprintf(qq(      <%s BGCOLOR=%s CLASS="right">%.2f</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $dbtable->[$j][$i], $tag);
      } elsif ($ticker_rows[$i]{'fmt'} == 2) {
        $rv .= sprintf(qq(      <%s BGCOLOR=%s CLASS="right">%+.2f%%</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $dbtable->[$j][$i], $tag);
      } elsif ($ticker_rows[$i]{'fmt'} == 3) {
        $rv .= sprintf(qq(      <%s BGCOLOR=%s CLASS="right">%+.2f</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $dbtable->[$j][$i], $tag);
      }
    }
    $rv .= sprintf(qq(    </TR>\n));
  }
  $rv .= sprintf(qq(  </TABLE>\n));
}

#########################################################################################
# get_summary_table
#   Build db query for the port_param table, query the db, fetch rows to build a hash
#   of hashes that contains port_param data.  Use this data to build a summary html
#   table.
#
#   Returns a string that is the html summary table.
#
#   No inputs in the argument list (uses globals)
#
sub get_summary_table {

  my $query;
  my $sth;
  my @dbrow = ();
  my $fileportname;
  my $i = 0;
  my $rv = '';
  my $fpn;
  my @list_fileportname_by_total;
  my $max_port_total;
  my $prev_port_total;
  my $cum_port_total = 0.0;
  my $rel_diff;
  my $max_diff;
  my $cum_pct;
  my $nav_string;
  my $row_color;

  my @port_param_describe;
  my %port_param_index;
  my $sel_ports = '';

  ### Build, prepare and execute describe port_param query.
  $query = 'DESCRIBE port_param';
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";
  while (@dbrow = $sth->fetchrow_array()) {
    push(@port_param_describe, $dbrow[0]);
    $port_param_index{$dbrow[0]} = $i++;
  }

  ### Build, prepare and execute the port_param query.
  foreach $fpn (@fileportnames_param) {
    $sel_ports .= sprintf("fileportname = '%s' OR ", $fpn);
  }
  $sel_ports = substr($sel_ports, 0, -3);
  $query = sprintf("SELECT %s FROM %s WHERE (%s) ORDER BY %s DESC", '*', 'port_param', $sel_ports, 'total');
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";
  while (@dbrow = $sth->fetchrow_array()) {
    $fileportname = $dbrow[1];
    for ($i = 0; $i <= $#dbrow; $i++) {
      $hash_port_param{$fileportname}{$port_param_describe[$i]} = $dbrow[$i];
    }
    push(@list_fileportname_by_total, $fileportname);
    $hash_port_param{$fileportname}{'color'} = $colors[$#list_fileportname_by_total];
    $cum_port_total += $hash_port_param{$fileportname}{'total'};
  }

  $rv =  sprintf(qq(<TABLE CLASS="sum_tab">\n));
  ### Add header row to table
  $rv .= sprintf(qq(<TR>\n));
  $rv .= sprintf(qq(  <TH>%s</TH>\n), $port_param_describe[$port_param_index{'fileportname'}]);  ### Name
  $rv .= sprintf(qq(  <TH>%s</TH>\n), $port_param_describe[$port_param_index{'total'}]);         ### Total
  $rv .= sprintf(qq(  <TH>%s</TH>\n), $port_param_describe[$port_param_index{'pct_daygain'}]);   ### Daygain%
  $rv .= sprintf(qq(  <TH>%s</TH>\n), $port_param_describe[$port_param_index{'daygain'}]);       ### Daygain
  $rv .= sprintf(qq(  <TH>%s</TH>\n), $port_param_describe[$port_param_index{'pct_gain'}]);      ### Gain%
  $rv .= sprintf(qq(  <TH>%s</TH>\n), $port_param_describe[$port_param_index{'gain'}]);          ### Gain
  $rv .= sprintf(qq(  <TH>%s</TH>\n), 'RelDiff');                                                ### Relative Difference
  $rv .= sprintf(qq(  <TH>%s</TH>\n), 'MaxDiff');                                                ### Max Difference
  $rv .= sprintf(qq(  <TH>%s</TH>\n), 'Cum%');                                                   ### Cumulative Percentage
  $rv .= sprintf(qq(</TR>\n));
  ### Add rows for each port to table
  for ($i = 0; $i <= $#list_fileportname_by_total; $i++) {
    $fileportname = $list_fileportname_by_total[$i];
    if ($i == 0) { 
      $max_port_total  = $hash_port_param{$fileportname}{'total'}; 
      $prev_port_total = $hash_port_param{$fileportname}{'total'}; 
    }
    $rel_diff = ($hash_port_param{$fileportname}{'total'}) - $prev_port_total;
    $max_diff = ($hash_port_param{$fileportname}{'total'}) - $max_port_total;
    $cum_pct = 100.0 * (($hash_port_param{$fileportname}{'total'}) / $cum_port_total);
    $row_color = color2hex($hash_port_param{$fileportname}{'color'});
    $rv .= sprintf(qq(<TR BGCOLOR="%s">\n), $row_color);
    $rv .= sprintf(qq(  <TD CLASS="left">%s</TD>\n),       $hash_port_param{$fileportname}{'fileportname'});  ### Name
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f</TD>\n),    $hash_port_param{$fileportname}{'total'});                      ### Total
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f%%</TD>\n),  $hash_port_param{$fileportname}{'pct_daygain'});                ### Daygain%
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f</TD>\n),    $hash_port_param{$fileportname}{'daygain'});                    ### Daygain
    $rv .= sprintf(qq(  <TD CLASS="right">%.1f%%</TD>\n),  $hash_port_param{$fileportname}{'pct_gain'});                   ### Gain%
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f</TD>\n),    $hash_port_param{$fileportname}{'gain'});                       ### Gain
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f</TD>\n),    $rel_diff);                                                     ### Relative Difference
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f</TD>\n),    $max_diff);                                                     ### Max Difference
    $rv .= sprintf(qq(  <TD CLASS="right">%.2f%%</TD>\n),  $cum_pct);                                                      ### Cumulative Percentage
    $rv .= sprintf(qq(</TR>\n));

    ### Remember previous port total for next time through the loop
    $prev_port_total = ($hash_port_param{$fileportname}{'total'}); 
  }
  ### Add TOTAL row to table
  $row_color = '#C8C0A0';
  $rv .= sprintf(qq(<TR>\n));
  $rv .= sprintf(qq(  <TD CLASS="total">%s</TD>\n), 'TOTAL');  ### Name
  $rv .= sprintf(qq(  <TD CLASS="total">%.2f</TD>\n), $cum_port_total);        ### Total
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Daygain%
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Daygain
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Gain%
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Gain
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Relative Difference
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Max Difference
  $rv .= sprintf(qq(  <TD CLASS="total"></TD>\n));                             ### Cumulative Percentage
  $rv .= sprintf(qq(</TR>\n));
  $rv .= sprintf(qq(</TABLE>\n));
  return($rv);
}

###################################################################################
# generate_chart
#
# Six inputs
#   o $title -- Title for chart
#   o $p_colors -- Pointer to list of colors
#   o $p_data -- Pointer to chart data array
sub generate_chart {
  my ($title, $p_colors, $p_data) = @_;
  (my $graph_width, my $graph_height) = split(/x/, $geom_param);
  my ($graph) = new GD::Graph::pie($graph_width, $graph_height);
  $graph->set( 
              #title             => $title,
               dclrs             => $p_colors,
               bgclr             => 'grey20',
               fgclr             => 'black',
               accentclr         => 'white',
               transparent       => $FALSE,
               labelclr          => 'white',
               axislabelclr      => 'white',
               textclr           => 'white',
             );
  $graph->set_label_font($font, 8);
  $graph->set_value_font($font, 8);
  print $q->header( 'image/png' );
  my $gd_pie = $graph->plot($p_data) || die "ERROR: Unable to plot. <" . $graph->error . ">";
  print $gd_pie->png;
}

###################################################################################
# generate_position_data
#
# Two inputs
#   o $fpn -- fileportname in question
#   o $p_data -- Pointer to chart data array
#   o $p_colors -- Pointer to list of colors
#   o $showcash -- TRUE/FALSE
sub generate_position_data {
  my ($fpn, $p_data, $p_colors, $showcash) = @_;
  my $query;
  my $cum_total;
  my $pp_table;
  my $tr_table;
  my $i;

  $query = sprintf("SELECT total,cash FROM port_param WHERE (fileportname = '%s')", $fpn);
  $pp_table = $dbh->selectall_arrayref($query);
  $cum_total = $pp_table->[0][0];
  if (! $showcash) { $cum_total -= $pp_table->[0][1]; }

  $query = sprintf("SELECT symbol,market_value FROM transaction_report WHERE (fileportname = '%s') ORDER BY market_value DESC", $fpn);
  $tr_table = $dbh->selectall_arrayref($query);

  for ($i = 0; $i <= $#{$tr_table}; $i++) {
    $p_data->[0][$i] = sprintf("%s %.1f%%", $tr_table->[$i][0], (100.0 * $tr_table->[$i][1] / $cum_total));
    $p_data->[1][$i] = $tr_table->[$i][1];
    $p_colors->[$i] = $colors[$i];
  }

  if ($showcash) {
    $p_data->[0][scalar(@{$tr_table})] = sprintf("%s %.1f%%", 'cash', (100.0 * $pp_table->[0][1] / $cum_total));
    $p_data->[1][scalar(@{$tr_table})] = $pp_table->[0][1];
    $p_colors->[scalar(@{$tr_table})] = 'green';
  }
}

###################################################################################
# generate_position_chart
#
# Four inputs
#   o $title -- Title for chart
#   o $p_colors -- Pointer to list of colors
#   o $p_data -- Pointer to chart data array
#   o $showcash -- TRUE/FALSE
sub generate_position_chart {
  my ($title, $p_colors, $p_data, $showcash) = @_;
  (my $graph_width, my $graph_height) = split(/x/, $geom_param);
  my ($graph) = new GD::Graph::pie($graph_width, $graph_height);
  if ($showcash) { $title .= ' + cash'; }
  $graph->set( 
               title             => $title,
               dclrs             => $p_colors,
               bgclr             => 'grey20',
               fgclr             => 'black',
               accentclr         => 'white',
               transparent       => $FALSE,
               labelclr          => 'white',
               axislabelclr      => 'white',
               textclr           => 'white',
             );
  $graph->set_label_font($font, 8);
  $graph->set_value_font($font, 8);
  print $q->header( 'image/png' );
  my $gd_pie = $graph->plot($p_data) || die "ERROR: Unable to plot. <" . $graph->error . ">";
  print $gd_pie->png;
}

#####################################################################################
# Non-global declarations
#####################################################################################
our $j;
our %hash_stats;
our $fpn;
our $pn;
our $query;
our $p_hash_port_param;
our @pie_data = ();
our @pie_colors = ();
our $cum_total = 0;
our $p = 0;

### Connect to DB.
$dbh = DBI->connect('dbi:mysql:track_port', 'blreams') or die "ERROR: Connection error: $DBI::errstr\n";

### Build %hash_list_ports from DB.
get_all_ports(\%hash_list_ports, \%hash_hash_ports);

### Untaint and process parameters.
untaint_params;

### Query DB.
$query = sprintf("SELECT fileportname,cash,total FROM port_param", $fpn);
$p_hash_port_param = $dbh->selectall_hashref($query, 'fileportname');

### Accumulate totals for percentage calc.
for ($p = 0; $p <= $#fileportnames_param; $p++) {
  $fpn = $fileportnames_param[$p];
  $cum_total += $p_hash_port_param->{$fpn}{'total'};
}

### Generate pie chart data.
for ($p = 0; $p <= $#fileportnames_param; $p++) {
  $fpn = $fileportnames_param[$p];
  $pn = $fpn;
  $pn =~ s/^.*:(.*)$/$1/;
  $pn =~ s/_combined$//;
  $pie_data[0][$p] = sprintf("%s %.1f%%", $pn, ($p_hash_port_param->{$fpn}{'total'} * 100.0 / $cum_total));
  $pie_data[1][$p] = $p_hash_port_param->{$fpn}{'total'};
  push(@pie_colors, $colors[$p]);
}

##################################################
### Below here is where we do the actual graphing.
##################################################
if ($plot_param eq 'html') {
  our $html_ticker_table = get_ticker_table();
  our $html_summary_table = get_summary_table();
  print $q->header( 'text/html' );
  html_header;
  printf(qq(<TABLE CLASS="sum_tab"><TR>\n));
  printf(qq(<TD>\n));
  printf("%s", $html_ticker_table);
  printf(qq(</TD><TD>\n));
  printf("%s", $html_summary_table);
  printf(qq(</TD><TD>\n));
  printf(qq(</TD></TR></TABLE>\n));
  printf(qq(<TABLE>\n));
  foreach $fpn (@fileportnames_param) {
    printf(qq(<TR>\n));
    html_body($fpn, 640, 480, 'positions_nocash');
    html_body($fpn, 640, 480, 'positions_cash');
    printf(qq(</TR>\n));
  }
  html_footer;

} elsif ($plot_param eq 'summary') { 
  generate_chart($graph_title, \@pie_colors, \@pie_data); 
} elsif ($plot_param eq 'positions_cash') {
  generate_position_data($fileportnames_param[0], \@pie_data, \@pie_colors, $TRUE);
  generate_position_chart($fileportnames_param[0], \@pie_colors, \@pie_data, $TRUE); 
} elsif ($plot_param eq 'positions_nocash') {
  generate_position_data($fileportnames_param[0], \@pie_data, \@pie_colors, $FALSE);
  generate_position_chart($fileportnames_param[0], \@pie_colors, \@pie_data, $FALSE); 
}

