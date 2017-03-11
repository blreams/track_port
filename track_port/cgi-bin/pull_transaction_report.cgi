#!/usr/bin/perl -T
# Copyright 2009 BLR.
# All rights reserved.
# This is unpublished, confidential BLR proprietary
# information.  Do not reproduce without written permission.
#
# file:         pull_transaction_report
#
# description:
#
# Modification History
#
# when      ver   who       what
# --------  ---   --------  -----------------------------------------
# 01/20/09  1.0   blreams   initial
# 02/01/09  1.1   blreams   added colors, horizontal bar charts, etc.
# 02/04/09  1.2   blreams   added summary table at top.
# 02/05/09  1.3   blreams   additions to summary table.
# 02/10/09  1.4   blreams   added columns, started using CSS.
# 02/11/09  1.5   blreams   added mouseover actions to summary table.
# 02/13/09  1.6   blreams   major rework of argument specification.
# 02/19/09  1.7   blreams   added ticker table
# 02/26/09  1.8   blreams   made ticker table one line
# 03/14/09  1.9   blreams   implemented multiplier logic
# 03/14/09  1.9a  blreams   Reordered get_all_ports function declaration.
# 03/14/09  1.10  blreams   Added port_chart links.
# 03/26/09  1.10a blreams   Added showname argument.
# 03/31/09  1.10b blreams   get_main_table fix for color of total gain in summary row.
# 04/03/09  1.10c blreams   cosmetic changes to the ticker and summary tables.
# 04/17/09  1.10d blreams   rearranged ticker table columns.
# 06/11/09  1.10e blreams   charts open in new windows/tabs.
# 07/24/09  1.11  blreams   left multiplier logic, but multiplier is 1.
# 07/25/09  1.11a blreams   added whee doggie check.
# 07/27/09  1.11b blreams   added pie chart and get_geom sub.
# 07/30/09  1.11c blreams   call port_pie.cgi to generate pie chart html.
# 08/03/09  1.11d blreams   Added showsector argument.
# 08/13/09  1.11e blreams   Started adding iphone support.
# 08/13/09  1.11f blreams   More iphone support.
# 08/14/09  1.11g blreams   iphone support and streamlining tables.
# 09/16/09  1.11h blreams   Added arg to toggle iPhone view.
# 10/20/09  1.11i blreams   Report TOTAL diff when method=diff.
# 10/26/09  1.11j blreams   Added constants for table column styles.
# 11/11/09  1.11k blreams   More iphone debugging and added some iphone cols.
# 01/01/10  1.11l blreams   Fixed chart_start calculation when in first month of year.
# 01/24/10  1.11m blreams   Added combined and geom parameters to port_pcie calls.
# 01/24/10  1.12a blreams   Fixed port_chart start_date arg for > 21 days into year.
# 02/10/10  1.12b blreams   Fixed bug iphone Symb links not containing symbol.
# 02/10/10  1.12c blreams   Removed extra cols from bottom row of summary table (iphone).
# 02/26/10  1.12d blreams   Added Mighty Whee Doggie!!! capability and pull time.
# 06/10/10  1.12e blreams   Modified iphone columns slightly to add mktval.
# 08/02/10  1.13  blreams   Added metadata tag so iphone will not auto link numbers.
# 08/02/10  1.13a blreams   Used metadata to set default width for iphone.
# 08/13/10  1.13b blreams   Added call to pagecounter.cgi
# 09/13/10  1.13c blreams   ^DJI quote is bad, changed timestamp to use last entry of $dbtable
# 10/05/10  1.14  blreams   Fixed bug w/ iPhone/Normal link at bottom not allowing column sort.
# 10/22/10  1.14a blreams   Finally fixed port_chart cmd to use 12/31/<previous year> instead of 01/01/<this year>.
# 02/25/11  1.14b blreams   Added button to call port_edit.cgi
# 02/20/13  1.14c blreams   Fixed pct_gain formula returned from DB to handle negative (short) shares.
# 08/28/13  1.14d blreams   Show fractional shares if they exist.
# 09/03/13  1.15  blreams   changed make_link_string to uc the symbol.
# 10/27/13  1.16  blreams   added ex_div column as needed.
# 10/27/13  1.16a blreams   added code to modify ex_div for display as needed.
# 11/04/13  1.16b blreams   minor tweak to ex_div modification.
# 11/04/13  1.16c blreams   tweak to recognize SAMSUNG-SGH as "iphone" (ie. mobile).
# 03/26/14  1.16d blreams   Show fractional shares if they exist in SOLD table.
# 03/28/14  1.17  blreams   Enabled jquery tablesorter support.
# 04/02/14  1.17a blreams   Put titleTable and mainTable inside containerTable.
# 04/02/14  1.17b blreams   Started implementing table_format from DB.
# 04/02/14  1.17c blreams   More implementation
# 04/03/14  1.17d blreams   More implementation
# 04/04/14  1.17e blreams   More implementation, added solddefault entries to table_format
# 04/04/14  1.17f blreams   More implementation, actually removed sold_fields and get_sold_tables
# 04/10/14  1.17g blreams   Added viewname parameter and supporting code.
# 04/16/14  1.17h blreams   Created cash row separate from total row in main table.
# 04/16/14  1.17i blreams   Cleanup and changed iphone var names to handheld.
# 04/17/14  1.17j blreams   Minor css styling of new cash row.
# 04/17/14  1.17k blreams   Oops, unstyled the change cells in total row.
# 05/02/14  1.18  blreams   Changed css to less.
# 05/04/14  1.18a blreams   More css changes.
# --------  ---   --------  -----------------------------------------
#-----------------------------------------------------------------------------
# Miscellaneous initialization
#-----------------------------------------------------------------------------
use strict;
#use warnings;
use CGI;
use DBI;
use Readonly;
use GD::Graph::colour;
use Time::CTime;
use Time::ParseDate;

our $script_name = $0; ($0 =~ /\//) && ($0 =~ /\/([^\/\s]*)\s*$/) && ($script_name = $1);
our $script_ver = '1.18a';
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
Readonly our $SECS_PER_DAY => (24 * 3600);

#-----------------------------------------------------------------------------
# Declarations
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Check for correct number of arguments
#-----------------------------------------------------------------------------
our $num_args = $#ARGV + 1;
if (($num_args != 1) && (($num_args < $min_args) || ($num_args > $max_args))) {
  printf(STDERR "ERROR: %s:  Incorrect number of arguments.\n", $script_name);
  &usage;
  exit 1;
}

our $flag_help = $FALSE;
our $flag_version = $FALSE;
our $flag_debug = $FALSE;
our $flag_verbose = $FALSE;
our $arg;
while ($#ARGV >= 0) {
  $arg = shift;
  if ($arg eq '--help') {
    usage;
    exit(0);
  }
  if ($arg eq '--version') {
    printf(STDERR "%s v%s\n", $script_name, $script_ver);
    exit(0);
  }
  if ($arg eq '--debug') {
    $flag_debug = $TRUE;
    next;
  }
  if ($arg eq '--verbose') {
    $flag_verbose = $TRUE;
    next;
  }
}

our $q = new CGI;
if ($flag_debug) {
# $q->param(watch => ('_ALL_'));
  $q->param(port  => ('fluffgazer','xcargot'));
# $q->param(spp   => ('esop','rsu','spp'));
# $q->param(serp  => ('blink'));
# $q->param(method => 'sum');
  $q->param(viewname => 'handheld');
# $q->param(combined => 'TRUE');
# $q->param(showname => 'FALSE');
# $q->param(showsector => 'FALSE');
# $q->param(handheld => 'FALSE');
# $q->param('sort' => '_symbol');
# $q->param('sold' => 'TRUE');
}

#########################################################################################
### The following are consided "global" variables in that they are declared here      ###
### before any of the subroutines...meaning they are part of the visible scope        ###
### of these subroutines.  The idea is keep from having to pass every little          ###
### argument.                                                                         ###
#########################################################################################
our $dbh;                     # DB handle, once connected.
our $method_param = '';       # The actual method parameter passed as _GET input.
our $viewname_param = '';     # The actual viewname parameter passed as _GET input.
our $combined_param = '';     # The actual combined parameter passed as _GET input.
our $showname_param = '';     # The actual showname parameter passed as _GET input.
our $showsector_param = '';   # The actual showsector parameter passed as _GET input.
our $handheld_param = undef;  # true (or false) if handheld parameter included as _GET input, otherwise undef
our $sort_param = '';         # The actual sort parameter passed as _GET input.
our $sold_param = '';         # The actual sold parameter passed as _GET input.
our %hash_params;             # Hash of the processed parameters.
our %hash_port_param;         # Hash of hashes containing queried port_param data.
our %hash_list_ports;         # Hash of lists, hash index is filename, list of ports in that file.
our %hash_list_ports_param;   # Subset of %hash_list_ports that is passed as parameter.
our %hash_hash_ports;         # Hash of hashes, hash index is filename, hash index is portname. Used to verify if parameter exists in DB.
our $quote_seconds;           # Time value represented by the quote date and time.
our $pull_seconds;            # Time value representing when the query is pulled.
our $whee_doggie_value;       # Used to indicate Whee Doggies label should be added.
our $handheld_agent;          # True if user_agent indicates handheld.
our $handheld_result;         # If $handheld_param is defined, use $handheld_param, else use $handheld_agent.
our $p_table_format;          # pointer to hash of hashes representing table_format DB table.
our $p_table_format_keys;     # pointer to ordered list of table_format keys.

### Get colors from /etc/X11/rgb.txt, then load up array of repeating colors
###   There are 20 colors that are repeated.  Each color has a corresponding
###   .gif file.  File is 1x1 pixel and is used for img html tag stretching.
GD::Graph::colour::read_rgb("/etc/X11/rgb.txt");
our @colors = (
# Blue              Purple          Red          Green             Brown
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
  'MidnightBlue',   'DarkOrchid4',  'DarkRed',   'DarkGreen',      'SaddleBrown',
  'MediumBlue',     'maroon4',      'firebrick', 'SpringGreen4',   'goldenrod4',
  'DeepSkyBlue4',   'VioletRed',    'coral3',    'ForestGreen',    'chocolate',
  'DodgerBlue',     'MediumOrchid', 'tomato',    'MediumSeaGreen', 'DarkOrange2',
);

#########################################################################################

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

#########################################################################################
# magnitude_string
#   Takes an integer and converts it to a string with appropriate magnitude indicator
#     $num -- integer to be converted.
sub magnitude_string {
  my ($num) = @_;
  my $s_num;
  if ($num > 1000000000) {
    $s_num = sprintf("%.3fB", $num / 1000000000);
  } elsif ($num > 1000000) {
    $s_num = sprintf("%.3fM", $num / 1000000);
  } elsif ($num > 1000) {
    $s_num = sprintf("%.3fK", $num / 1000);
  } else {
    $s_num = sprintf("%d", $num);
  }
  return($s_num);
}

#########################################################################################
# change_exdiv
#   Takes the ex_div date and modifies it if in the past (assumes quarterly dividend)
#   Modification is as follows:
#     o if date is in the future, leave it alone.
#     o if date is within 1 month of today, leave it alone.
#     o if date is older than that, add 91 day increments until it becomes a future date.
#
#     $exdiv -- date to be checked/modified
sub change_exdiv {
  my ($exdiv) = @_;
  my $seconds_exdiv = parsedate($exdiv);
  my $seconds_now = parsedate("now");

  if (! $seconds_exdiv) { 
    return($exdiv);
  } elsif ($seconds_exdiv >= ($seconds_now - ($SECS_PER_DAY * 30))) {
    return($exdiv);
  } else {
    while ($seconds_exdiv < ($seconds_now - ($SECS_PER_DAY * 30))) {
      $seconds_exdiv += $main::SECS_PER_DAY * 91;
    }
    $exdiv = '*' . strftime("%Y-%m-%d", localtime($seconds_exdiv));
  }
  return($exdiv);
}

#########################################################################################
# make_link_string
#   Takes a link_label and a symbol as arguments.
#   link_label specifies which link to create.  Current supported link_label values
#   are as follows:
#     yahoo_quote
#     yahoo_key_stats
#     marketwatch_chart
#     yahoo_basic_chart
sub make_link_string {
  my ($link_label, $symbol) = @_;
  my $link_string = '';

  $symbol = lc($symbol);
  if ($link_label eq 'yahoo_quote') {
    $link_string = sprintf("http://finance.yahoo.com/q?s=%s", uc($symbol));
  } elsif ($link_label eq 'yahoo_key_stats') {
    $link_string = sprintf("http://finance.yahoo.com/q/ks?s=%s", uc($symbol));
  } elsif ($link_label eq 'yahoo_basic_chart') {
    $link_string = sprintf("http://finance.yahoo.com/q/bc?s=%s&amp;t=1y", uc($symbol));
  } elsif ($link_label eq 'marketwatch_chart') {
    $link_string = sprintf("http://www.marketwatch.com/tools/quotes/intchart.asp?submitted=true&amp;intflavor=advanced&amp;symb=%s&amp;origurl=%%2Ftools%%2Fquotes%%2Fintchart.asp&amp;time=12&amp;freq=1&amp;startdate=10%%2F17%%2F2003&amp;enddate=10%%2F17%%2F2008&amp;hiddenTrue=&amp;comp=Enter+Symbol(s)%%3A&amp;compidx=aaaaa~0&amp;compind=aaaaa~0&amp;uf=7168&amp;ma=5&amp;maval=50&amp;lf=16777216&amp;lf2=8388608&amp;lf3=67108864&amp;type=2&amp;size=3&amp;optstyle=380", uc($symbol));
  }
  return($link_string);
}


#########################################################################################
# whee_doggie_check
#   Returns  0 if not applicable or no whee doggie.
#   Returns  1 if fluffgazer gets whee doggie.
#   Returns -1 if xcargot gets whee doggie.
#   Returns  2 if fluffgazer gets mighty whee doggie.
#   Returns -2 if xcargot gets mighty whee doggie.
sub whee_doggie_check {
  my $query;
  my @list_ports_sorted = ();
  my $p_db_totals;
  my $fg_diff;
  my $xc_diff;

  @list_ports_sorted = sort(@{$hash_params{'ports'}});

  if (($list_ports_sorted[0] =~ /^port:fluffgazer/) && ($list_ports_sorted[1] =~ /^port:xcargot/)) {
    $query = sprintf("SELECT total FROM port_history WHERE (fileportname = 'port:fluffgazer') ORDER BY date DESC LIMIT 2");
    $p_db_totals = $dbh->selectcol_arrayref($query);
    $fg_diff = $p_db_totals->[0] - $p_db_totals->[1];
    $query = sprintf("SELECT total FROM port_history WHERE (fileportname = 'port:xcargot') ORDER BY date DESC LIMIT 2");
    $p_db_totals = $dbh->selectcol_arrayref($query);
    $xc_diff = $p_db_totals->[0] - $p_db_totals->[1];
    if (($fg_diff > 0.0) && (($fg_diff - $xc_diff) > 1000.0)) { return(2); }
    if (($fg_diff > 0.0) && ($fg_diff > $xc_diff))    { return(1); }
    if (($xc_diff > 0.0) && (($xc_diff - $fg_diff) > 1000.0)) { return(-2); }
    if (($xc_diff > 0.0) && ($xc_diff > $fg_diff))    { return(-1); }
  }
  return(0);
}

#########################################################################################
# html_header
#   Create the header for the main html file.  Also
sub html_header {
  printf(qq(<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n));
  printf(qq(<html>\n));
  printf(qq(<head>\n));
  printf(qq(  <meta http-equiv="content-type" content="text/html;charset=iso-8859-1"/>\n));
  printf(qq(  <meta name="generator" content="BLR Tool"/>\n));
  printf(qq(  <meta name="format-detection" content="telephone=no"/>\n));
  printf(qq(  <meta name="viewport" content="width=500"/>\n));
  printf(qq(  <title>%s v%s</title>\n), $script_name, $script_ver);
  #BLR - Commented these and used pre-compiled less when Safari stopped working.
  #printf(qq(  <script type="text/javascript">less = { env: 'development' };</script>\n));
  #printf(qq(  <link rel="stylesheet/less" type="text/css" href="/css/track_port_less.css" />\n));
  #printf(qq(  <script type="text/javascript" src="/js/less.js"></script>\n));
  printf(qq(  <link rel="stylesheet" type="text/css" href="/css/track_port_less.css" />\n));
  printf(qq(  <!--\n));
  printf(qq(  <link rel="stylesheet" type="text/css" href="/css/track_port.css" />\n));
  printf(qq(  -->\n));
  printf(qq(  <script type="text/javascript" src="/js/jquery.js"></script>\n));
  printf(qq(  <script type="text/javascript" src="/js/jquery.tablesorter.js"></script>\n));
  printf(qq(  <script type="text/javascript">\n));
  printf(qq/    \$(document).ready(function() { \n/);
  printf(qq/      \$('.mainTable').tablesorter({\n/);
  printf(qq/          debug: true,\n/);
  printf(qq/          sortInitialOrder: "desc",\n/);
  printf(qq/          widgets:['zebra'],\n/);
  printf(qq/          headers: {\n/);
  my $j = 0;
  foreach my $position (@{$p_table_format_keys}) {
    if (! $p_table_format->{$position}{'enabled'}) { next; }
    if ($handheld_result) {
      if (! $p_table_format->{$position}{'handheld'}) { next; }
    } else {
      if (($p_table_format->{$position}{'fld'} eq 'name') && (! $hash_params{'showname'})) { next; }
      if (($p_table_format->{$position}{'fld'} eq 'sector') && (! $hash_params{'showsector'})) { next; }
    }
    printf(qq/             %d: { sorter: "%s" },\n/, $j, ($p_table_format->{$position}{'sorter'} ? $p_table_format->{$position}{'sorter'} : 'false'));
    $j++;
  }
  printf(qq/          }\n/);
  printf(qq/       });\n/);
  printf(qq/      });\n/);
  printf(qq(  </script>\n));
  printf(qq(  <script type="text/javascript">\n));
  printf(qq/    \$(document).ready(function() { \n/);
  printf(qq/      \$('table.mainTable tbody tr').mouseover(function() { \n/);
  printf(qq/        \$(this).addClass('highlight'); \n/);
  printf(qq/      }).mouseout(function() { \n/);
  printf(qq/        \$(this).removeClass('highlight'); \n/);
  printf(qq/      });\n/);
  printf(qq/    });\n/);
  printf(qq(  </script>\n));
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

#########################################################################################
# info_table
#   Used for exposing information.
sub info_table {
  my $handheld_string = '&amp;handheld=' . (($handheld_result) ? 'FALSE' : 'TRUE');
  printf(qq(<table>\n));
  printf(qq(<tr><td><a href="/cgi-bin/pull_transaction_report.cgi?%s%s">%s</a></td></tr>\n), $hash_params{'raw_sans_sort'}, $handheld_string, ($handheld_result?'Normal':'Handheld'));
  printf(qq(</table>\n));
}

#########################################################################################
# html_footer
#   Create the html footer.
sub html_footer {
  printf(qq(</body>\n));
  printf(qq(</html>\n));
}

##############################################################################
# get_port_edit_cmd
#   Build cgi command for port_edit
#
#   Returns the port_edit.cgi command.
#
sub get_port_edit_cmd {
  my $cmd;
  my $f;
  my $first_time = $TRUE;

  $cmd = sprintf("http://%s/scgi-bin/port_edit.cgi", $ENV{'HTTP_HOST'});
  foreach my $f (keys(%hash_list_ports_param)) {
    $cmd .= ($first_time) ? '?' : '&amp;';
    $cmd .= sprintf("file=%s", $f);
    $first_time = $FALSE;
  }
  return($cmd);
}

##############################################################################
# get_port_sold_cmd
#   Build cgi command for showing sold positions.
#
#   Returns the pull_transaction_report.cgi command.
#
sub get_port_sold_cmd {
  my $cmd;
  my $fpn;
  my $f;
  my $p;
  my $i;

  $cmd = sprintf("pull_transaction_report.cgi?");
  for ($i = 0; $i <= $#{$hash_params{'ports'}}; $i++) {
    $fpn = $hash_params{'ports'}[$i];
    $fpn =~ s/_combined//;
    ($f, $p) = split(/:/, $fpn);
    $cmd .= sprintf("%s=%s&amp;", $f, $p);
  }
  $cmd .= sprintf("sold=TRUE");
  return($cmd);
}

##############################################################################
# get_port_chart_cmd
#   Build cgi command for port_chart
#
#   Lone argument is a fileportname.  If argument is blank, then assume
#   multiple fileportnames based on hash_params.
#
#   Returns the port_chart.cgi command.
#
sub get_port_chart_cmd {
  my ($fpn) = @_;
  my $cmd;
  my $f;
  my $p;
  my $i;

  $cmd = "port_chart.cgi?";
  if (! $fpn) {
    for ($i = 0; $i <= $#{$hash_params{'ports'}}; $i++) {
      $fpn = $hash_params{'ports'}[$i];
      $fpn =~ s/_combined//;
      ($f, $p) = split(/:/, $fpn);
      $cmd .= sprintf("%s=%s&amp;", $f, $p);
    }
  } else {
    $fpn =~ s/_combined//;
    ($f, $p) = split(/:/, $fpn);
    $cmd .= sprintf("%s=%s&amp;", $f, $p);
  }
  $cmd .= sprintf("method=%s&amp;", $hash_params{'method'});
  $cmd .= sprintf("start=%s&amp;", $main::chart_start);
  $cmd .= sprintf("end=%s", $main::chart_end);
  return($cmd);
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
#   Three outputs in the argument list:
#     $p_method -- reference to scalar to hold method parameter string.
#     $p_viewname -- reference to scalar to hold viewname parameter string.
#     $p_combined -- reference to scalar to hold combined parameter string.
#     $p_showname -- reference to scalar to hold showname parameter string.
#     $p_showsector -- reference to scalar to hold showsector parameter string.
#     $p_handheld -- reference to scalar to hold handheld parameter string.
#     $p_sort -- reference to scalar to hold sort parameter string.
#     $p_sold -- reference to scalar to hold sold parameter string.
#
sub untaint_params {
  my ($p_method, $p_viewname, $p_combined, $p_showname, $p_showsector, $p_handheld, $p_sort, $p_sold) = @_;

  my ($method)     = $q->param('method') =~ /^(diff|sum|none)$/;
  my ($viewname)   = $q->param('viewname') =~ /^(\w+)$/;
  my ($combined)   = $q->param('combined') =~ /^(TRUE|FALSE)$/;
  my ($showname)   = $q->param('showname') =~ /^(TRUE|FALSE)$/;
  my ($showsector) = $q->param('showsector') =~ /^(TRUE|FALSE)$/;
  my ($handheld)   = $q->param('handheld') =~ /^(TRUE|FALSE|)$/;
  my ($sort)       = $q->param('sort') =~ /^(\w+)$/;
  my ($sold)       = $q->param('sold') =~ /^(TRUE|FALSE|)$/;
  my (@ports);
  my $f;
  my $p;

  foreach $f (keys %hash_list_ports) {
    @ports = $q->param($f);
    foreach $p (@ports) {
      if (! ($p =~ /^([-\w_]+)$/)) { next; }
      if ($p eq '_ALL_') {
        $hash_list_ports_param{$f} = ();
        push(@{$hash_list_ports_param{$f}}, $p);
        last;
      } elsif (($hash_hash_ports{$f}{$p}) || ($p eq '_ALL_')) {
        push(@{$hash_list_ports_param{$f}}, $p);
      }
    }
  }

  if ($handheld eq '') { 
    $handheld = undef;
  } elsif ($handheld eq 'FALSE') {
    $handheld = 0;
  } else {
    $handheld = 1;
  }

  if ($method)     { $$p_method = $method; }
  if ($viewname)   { $$p_viewname = $viewname; }
  if ($combined)   { $$p_combined = $combined; }
  if ($showname)   { $$p_showname = $showname; }
  if ($showsector) { $$p_showsector = $showsector; }
                   { $$p_handheld = $handheld; }
  if ($sort)       { $$p_sort = $sort; }
  if ($sold)       { $$p_sold = $sold; }
}

#########################################################################################
# get_geom
#   Calculate a geometry string for use w/ port_pie.cgi call.  Value is based on 
#   number of ports displayed.
#
sub get_geom {
  my $rv = '';
  my $num_ports = scalar(@{$hash_params{'ports'}});

  if    ($num_ports <= 3)  { return('200x100'); }
  elsif ($num_ports >= 14) { return('400x200'); }
  my $width = 200 + (20 * ($num_ports - 3));
  my $height = $width / 2;
  return(sprintf("%dx%d", $width, $height));
}


#########################################################################################
# process_params
#   parse each parameter and build a hash to hold them.
#
#   Three inputs in the argument list:
#     $method -- method parameter string.
#     $viewname -- viewname parameter string.
#     $combined -- combined parameter string.
#     $showname -- showname parameter string.
#     $showsector -- showsector parameter string.
#     $handheld -- handheld parameter string.
#     $sort -- sort parameter string.
#     $sold -- sold parameter string.
#   Also use global %hash_list_ports_param.
#
#   No outputs in the argument list:
#     But, we do load the global %hash_params.
#
sub process_params {
  my ($method, $viewname, $combined, $showname, $showsector, $handheld, $sort, $sold) = @_;
  my $filename;
  my $portname;
  my @portnames;
  my @fileportnames;
  my $fileportname;
  my $c = 0;
  my $f;
  my $p;
  my @sorted_ports;
  my $combined_string;
  my $showname_string;
  my $showsector_string;
  my $sold_string;
  my $viewname_string;

  ### Parse combined parameter
  if ((! $combined) || ($combined eq 'TRUE')) {
    $hash_params{'combined'} = $TRUE;
  } else {
    $hash_params{'combined'} = $FALSE;
  }

  ### Parse showname parameter
  if ((! $showname) || ($showname eq 'FALSE')) {
    $hash_params{'showname'} = $FALSE;
  } else {
    $hash_params{'showname'} = $TRUE;
  }

  ### Parse showsector parameter
  if ((! $showsector) || ($showsector eq 'FALSE')) {
    $hash_params{'showsector'} = $FALSE;
  } else {
    $hash_params{'showsector'} = $TRUE;
  }

  ### Parse sold parameter
  if (($sold) && ($sold eq 'TRUE')) {
    $hash_params{'sold'} = $TRUE;
  } else {
    $hash_params{'sold'} = $FALSE;
  }

  if (defined($handheld)) {
    if (! $handheld) {
      $hash_params{'handheld'} = $FALSE;
    } else {
      $hash_params{'handheld'} = $TRUE;
    }
  }

  $hash_params{'raw_sans_sort'} = '';
  foreach $f (keys %hash_list_ports_param) {
    if ($hash_list_ports_param{$f}[0] eq '_ALL_') { $hash_list_ports_param{$f} = $hash_list_ports{$f}; }
    foreach $p (@{$hash_list_ports_param{$f}}) {
      ### build fileportname and append to list.
      $fileportname = sprintf("%s:%s", $f, ($hash_params{'combined'} ? ($p . '_combined') : $p));
      push(@fileportnames, $fileportname);
      $hash_port_param{$fileportname}{'color'} = $colors[$c];
      $c = ($c + 1) % scalar(@colors);
      $hash_params{'raw_sans_sort'} .= sprintf("%s=%s&amp;", $f, $p);
    }
  }
  $hash_params{'ports'} = \@fileportnames;          # put ref to fileportnames list in parameter hash.
  $hash_params{'raw_ports'} = $hash_params{'raw_sans_sort'};
  $hash_params{'raw_ports'} = substr($hash_params{'raw_sans_sort'},0,(length($hash_params{'raw_sans_sort'}) - 5));

  # TODO Need to check viewname value against entries in database.
  $hash_params{'viewname'} = $viewname;

  ### Parse method parameter
  if (! $method) {
    if (scalar(@fileportnames) == 2) {
      $hash_params{'method'} = 'diff';
    } else {
      $hash_params{'method'} = 'none';
    }
  } else {
    $hash_params{'method'} = $method;
  }

  ### Parse sort parameter
  $hash_params{'sortdir'} = 'desc';
  if (! $sort) {
    $hash_params{'sort'} = 'pct_chg';
  } else {
    $hash_params{'sort'} = $sort;
    if ($sort =~ /^\_/) {
      $hash_params{'sort'} = substr($sort, 1);
      $hash_params{'sortdir'} = 'asc';
    }
  }

  ### Create a copy of the raw argument string sans sort
  $combined_string = $hash_params{'combined'}?'':'&amp;combined=FALSE';
  $showname_string = $hash_params{'showname'}?'&amp;showname=TRUE':'';
  $showsector_string = $hash_params{'showsector'}?'&amp;showsector=TRUE':'';
  $sold_string = $hash_params{'sold'}?'&amp;sold=TRUE':'';
  $viewname_string = $hash_params{'viewname'} ? ('&amp;viewname=' . $hash_params{'viewname'}) : '';
  $hash_params{'raw_sans_sort'} .= sprintf("method=%s%s%s%s%s%s", $hash_params{'method'}, $combined_string, $showname_string, $showsector_string, $sold_string, $viewname_string);

  return($TRUE);
}

#########################################################################################
# get_table_format
#   Query DB to get customized table format.
#
#   There are two references returned
#     o $p_tf -- pointer to %table_format which is a hash of hashes.  Outer index is
#                position.  Inner index is field name from DB table.
#     o $p_tfk -- pointer to sorted list of table_format indexes.
#########################################################################################
sub get_table_format {
  my $viewname;
  if ($hash_params{'viewname'}) {
    $viewname = $hash_params{'viewname'};
  } elsif ($handheld_result) {
    $viewname = 'handheld';
  } else {
    $viewname = 'default';
  }
  if ($hash_params{'sold'}) { $viewname = 'solddefault'; }
  my $query = sprintf("SELECT * FROM table_format WHERE ((enabled) && (viewname = '%s')) ORDER BY position", $viewname);
  my $p_tf = $dbh->selectall_hashref($query, 'position');
  my @tfk = sort {$a <=> $b} keys(%$p_tf);
  return($p_tf, \@tfk);
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
  # NOTE: Use last entry $dbtable->[$#{$dbtable}].
  ($h, $m, $s) = split(/:/, $dbtable->[$#{$dbtable}][$#ticker_rows + 2]);
  if ($h < 5) { $h += 12; }
  $quote_seconds = parsedate($dbtable->[$#{$dbtable}][$#ticker_rows + 1] . ' ' . sprintf("%02d:%02d:%02d", $h, $m, $s));
  $pull_seconds = parsedate("now");

  $rv = sprintf(qq(  <table class="tick_tab">\n));
  $rv .= sprintf(qq(    <tr>\n));
  for ($i = 0; $i <= $#ticker_rows; $i++) {
    $rv .= sprintf(qq(<th>%s</th>\n), $ticker_rows[$i]{'hdr'});
  }
  $rv .= sprintf(qq(    </tr>\n));
  for ($j = 0; $j < scalar(@{$dbtable}); $j++) {
    $rv .= sprintf(qq(    <tr>\n));
    for ($i = 0; $i <= $#ticker_rows; $i++) {
      $tag = 'td';
      if ($ticker_rows[$i]{'fmt'} == 0) {
        $href = sprintf(qq(<a href="http://finance.yahoo.com/q?s=%s" target= "_blank">%s</a>), lc($dbtable->[$j][$i]), $dbtable->[$j][$i]);
        $rv .= sprintf(qq(      <%s bgcolor="%s" class="left">%s</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $href, $tag);
      } elsif ($ticker_rows[$i]{'fmt'} == 1) {
        $rv .= sprintf(qq(      <%s bgcolor="%s" class="right">%.2f</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $dbtable->[$j][$i], $tag);
      } elsif ($ticker_rows[$i]{'fmt'} == 2) {
        $rv .= sprintf(qq(      <%s bgcolor="%s" class="right">%+.2f%%</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $dbtable->[$j][$i], $tag);
      } elsif ($ticker_rows[$i]{'fmt'} == 3) {
        $rv .= sprintf(qq(      <%s bgcolor="%s" class="right">%+.2f</%s>\n), $tag, calc_bgcolor($dbtable->[$j][$color_col], 0.1, 10.0), $dbtable->[$j][$i], $tag);
      }
    }
    $rv .= sprintf(qq(    </tr>\n));
  }
  $rv .= sprintf(qq(  </table>\n));
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
  my $filename;
  my $portname;
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
  my $cgi_chart;
  my $cgi_edit;
  my $cgi_sold;
  my $row_color;

  my @port_param_describe;
  my %port_param_index;
  my $sel_ports = '';
  my $port_chart_cmd;
  my $port_edit_cmd;
  my $port_sold_cmd;
  my $print_total;

  ### Build, prepare and execute describe port_param query.
  $query = 'DESCRIBE port_param';
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";
  while (@dbrow = $sth->fetchrow_array()) {
    push(@port_param_describe, $dbrow[0]);
    $port_param_index{$dbrow[0]} = $i++;
  }

  ### Build, prepare and execute the port_param query.
  foreach $fpn (@{$hash_params{'ports'}}) {
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
    $cum_port_total += ($hash_port_param{$fileportname}{'total'});
  }

  $rv =  sprintf(qq(<table class="sum_tab">\n));
  ### Add header row to table
  $rv .= sprintf(qq(<tr>\n));
  $rv .= sprintf(qq(  <th>%s</th>\n), 'Name');                                                   ### Name
  $rv .= sprintf(qq(  <th>%s</th>\n), 'Total');                                                  ### Total
  $rv .= sprintf(qq(  <th>%s</th>\n), '%DGain');                                                 ### Daygain%
  $rv .= sprintf(qq(  <th>%s</th>\n), 'DGain');                                                  ### Daygain
  $rv .= sprintf(qq(  <th>%s</th>\n), '%Gain');                                                  ### Gain%
  $rv .= sprintf(qq(  <th>%s</th>\n), 'Gain');                                                   ### Gain
  if (! $handheld_result) {
    $rv .= sprintf(qq(  <th>%s</th>\n), 'RelDiff');                                              ### Relative Difference
    $rv .= sprintf(qq(  <th>%s</th>\n), 'MaxDiff');                                              ### Max Difference
    $rv .= sprintf(qq(  <th>%s</th>\n), 'Cum%');                                                 ### Cumulative Percentage
  }
  $rv .= sprintf(qq(</tr>\n));
  ### Add rows for each port to table
  for ($i = 0; $i <= $#list_fileportname_by_total; $i++) {
    $fileportname = $list_fileportname_by_total[$i];
    ($filename, $portname) = split(/:/, $fileportname);
    if (! $portname) { $portname = $filename; }
    $portname =~ s/_combined$//;
    $port_chart_cmd = get_port_chart_cmd($fileportname);
    if ($i == 0) { 
      $max_port_total  = $hash_port_param{$fileportname}{'total'}; 
      $prev_port_total = $hash_port_param{$fileportname}{'total'}; 
    }
    $rel_diff = ($hash_port_param{$fileportname}{'total'}) - $prev_port_total;
    $max_diff = ($hash_port_param{$fileportname}{'total'}) - $max_port_total;
    $cum_pct = 100.0 * (($hash_port_param{$fileportname}{'total'}) / $cum_port_total);
    $row_color = color2hex($hash_port_param{$fileportname}{'color'});
    $cgi_chart = sprintf(qq(onmouseover="ChangeColor(this,true,'%s');" onmouseout="ChangeColor(this,false,'%s');" onclick="DoNav('%s','%s');"), $row_color, $row_color, $port_chart_cmd, ($fileportname . '_chart_window'));
    $rv .= sprintf(qq(<tr bgcolor="%s">\n), $row_color);
    $rv .= sprintf(qq(  <td class="left" %s>%s</td>\n),    $cgi_chart, $portname);                                         ### Name
    $rv .= sprintf(qq(  <td class="right">%.2f</td>\n),    $hash_port_param{$fileportname}{'total'});                      ### Total
    $rv .= sprintf(qq(  <td class="right">%.2f%%</td>\n),  $hash_port_param{$fileportname}{'pct_daygain'});                ### Daygain%
    $rv .= sprintf(qq(  <td class="right">%.2f</td>\n),    $hash_port_param{$fileportname}{'daygain'});                    ### Daygain
    $rv .= sprintf(qq(  <td class="right">%.1f%%</td>\n),  $hash_port_param{$fileportname}{'pct_gain'});                   ### Gain%
    $rv .= sprintf(qq(  <td class="right">%.2f</td>\n),    $hash_port_param{$fileportname}{'gain'});                       ### Gain
    if (! $handheld_result) {
      $rv .= sprintf(qq(  <td class="right">%.2f</td>\n),    $rel_diff);                                                   ### Relative Difference
      $rv .= sprintf(qq(  <td class="right">%.2f</td>\n),    $max_diff);                                                   ### Max Difference
      $rv .= sprintf(qq(  <td class="right">%.2f%%</td>\n),  $cum_pct);                                                    ### Cumulative Percentage
    }
    $rv .= sprintf(qq(</tr>\n));

    ### Remember previous port total for next time through the loop
    $prev_port_total = ($hash_port_param{$fileportname}{'total'}); 
  }
  ### Add TOTAL row to table
  $print_total = $cum_port_total;
  if ($hash_params{'method'} eq 'diff') { $print_total = -1 * $max_diff; }
  $port_chart_cmd = get_port_chart_cmd();
  $port_edit_cmd = get_port_edit_cmd();
  $port_sold_cmd = get_port_sold_cmd();
  $row_color = '#C8C0A0';
  $cgi_chart = sprintf(qq(onmouseover="ChangeColor(this,true,'%s');" onmouseout="ChangeColor(this,false,'%s');" onclick="DoNav('%s','total_chart_window');"), $row_color, $row_color, $port_chart_cmd);
  $cgi_edit = sprintf(qq(onmouseover="ChangeColor(this,true,'%s');" onmouseout="ChangeColor(this,false,'%s');" onclick="DoNav('%s','total_chart_window');"), $row_color, $row_color, $port_edit_cmd);
  $cgi_sold = sprintf(qq(onmouseover="ChangeColor(this,true,'%s');" onmouseout="ChangeColor(this,false,'%s');" onclick="DoNav('%s','total_chart_window');"), $row_color, $row_color, $port_sold_cmd);
  $rv .= sprintf(qq(<tr>\n));
  $rv .= sprintf(qq(  <td class="total" %s>%s</td>\n), $cgi_chart, 'TOTAL');     ### Name
  $rv .= sprintf(qq(  <td class="right">%.2f</td>\n), $print_total);             ### Total
  $rv .= sprintf(qq(  <td class="totalcenter" %s>%s</td>\n), $cgi_edit, 'EDIT'); ### Daygain%
  $rv .= sprintf(qq(  <td class="totalcenter" %s>%s</td>\n), $cgi_sold, 'SOLD'); ### Daygain
  $rv .= sprintf(qq(  <td class="total"></td>\n));                               ### Gain%
  $rv .= sprintf(qq(  <td class="total"></td>\n));                               ### Gain
  if (! $handheld_result) {
    $rv .= sprintf(qq(  <td class="total"></td>\n));                             ### Relative Difference
    $rv .= sprintf(qq(  <td class="total"></td>\n));                             ### Max Difference
    $rv .= sprintf(qq(  <td class="total"></td>\n));                             ### Cumulative Percentage
  }
  $rv .= sprintf(qq(</tr>\n));
  $rv .= sprintf(qq(</table>\n));
  return($rv);
}


#########################################################################################
# get_main_tables
#   Builds db query for the main report tables.  Queries the db, parses out the data
#   and stores the html table structures in an anonymous hash.
#   Returns a pointer to that hash.
#
#   No inputs in the argument list (uses globals)
#
sub get_main_tables {
  my $f;
  my $r;
  my $p_dbrow;
  my $sth;
  my $query;
  my $fileportname;
  my $filename;
  my $portname;
  my $table_format_fields_string;
  my $p_hht;

  my $bg;
  my $symbol;
  my $cagr;
  my $p = 0;
  my $port_color;
  my $cw;
  my $color_pct_daygain;
  my $color_pct_gain;
  my $whee_doggie;
  my $table;
  my $sorter;

  my $dbg_message;
  my $handheld_fields = 0;

  ### Build select_field list for db query
  foreach my $position (@{$p_table_format_keys}) {
    if ($p_table_format->{$position}{'sel'}) {
      $table_format_fields_string .= sprintf("%s AS %s,", $p_table_format->{$position}{'sel'}, $p_table_format->{$position}{'fld'});
    } else {
      $table_format_fields_string .= $p_table_format->{$position}{'fld'} . ',';
    }
    if ($p_table_format->{$position}{'handheld'}) { $handheld_fields++; }
  }
  chop $table_format_fields_string;

  ### Loop over each one of the ports arguments
  foreach $fileportname (@{$hash_params{'ports'}}) {
    if ($hash_params{'sold'}) { $fileportname =~ s/_combined$//; }
    $whee_doggie = '';
    if ($whee_doggie_value) {
      if ($fileportname =~ /^port:fluffgazer/) {
        if ($whee_doggie_value == 1) {
          if (! $handheld_result) { $whee_doggie = ' -- Whee Doggies!!!'; } else { $whee_doggie = '-WD';}
        } elsif ($whee_doggie_value == 2) {
          if (! $handheld_result) { $whee_doggie = ' -- Mighty Whee Doggies!!!'; } else { $whee_doggie = '-MWD';}
        }
      }
      if ($fileportname =~ /^port:xcargot/) { 
        if ($whee_doggie_value == -1) {
          if (! $handheld_result) { $whee_doggie = ' -- !!!seiggoD eehW'; } else { $whee_doggie = '-DW';}
        } elsif ($whee_doggie_value == -2) {
          if (! $handheld_result) { $whee_doggie = ' -- !!!seiggoD eehW ythgiM'; } else { $whee_doggie = '-DWM';}
        }
      }
    }
    ($filename, $portname) = split(/:/, $fileportname);
    if (! $portname) { $portname = $filename; }
    $portname =~ s/_combined$//;
    $port_color = $colors[$p];
    ### Put title and main table inside a table.
    $p_hht->{$fileportname} = qq(<table class="containerTable" border="0" width="100%">\n);
    $p_hht->{$fileportname} .= qq(<tr><td>\n);
    ### Give TABLE a title
    $p_hht->{$fileportname} .= qq(<table class="titleTable" border="1">\n);
    $p_hht->{$fileportname} .= sprintf(qq(<tr bgcolor="%s">), color2hex($port_color));
    $p_hht->{$fileportname} .= sprintf(qq(<th nowrap><font size="1" color="#FFFFFF">%s</font></th>), "v$script_ver");
    $p_hht->{$fileportname} .= sprintf(qq(<th nowrap><font size="1" color="#FFFFFF">%s</font></th>), strftime("%c", $quote_seconds));
    if (! $handheld_result) {
      $p_hht->{$fileportname} .= sprintf(qq(<th nowrap><font size="1" color="#FFFFFF">%s</font></th>), strftime("%c", $pull_seconds));
      $p_hht->{$fileportname} .= sprintf(qq(<th width="99%"><font size="4" color="#FFFFFF">%s%s</font></th>), $portname, $whee_doggie);
    } else {
      $p_hht->{$fileportname} .= sprintf(qq(<th width="99%"><font size="4" color="#FFFFFF">%s%s</font></th>), $portname, $whee_doggie);
    }
    $p_hht->{$fileportname} .= "</tr>\n";
    $p_hht->{$fileportname} .= sprintf(qq(</table>\n));
    $p_hht->{$fileportname} .= qq(</td></tr>\n);

    ### Start TABLE html and add header row
    $p_hht->{$fileportname} .= qq(<tr><td>\n);
    $p_hht->{$fileportname} .= qq(<table class="mainTable" border="1">\n);
    $p_hht->{$fileportname} .= qq(  <thead>\n);

    ### Add Header row to TABLE
    $p_hht->{$fileportname} .= "  <tr>\n";
    foreach my $position (@{$p_table_format_keys}) {
      if (($handheld_result) && (! $p_table_format->{$position}{'handheld'})) { next; }
      if (($p_table_format->{$position}{'fld'} eq 'name') && (! $hash_params{'showname'})) { next; }
      if (($p_table_format->{$position}{'fld'} eq 'sector') && (! $hash_params{'showsector'})) { next; }
      $cw = '';
      if ($p_table_format->{$position}{'fld'} =~ /^hilo/) { $cw = ' width="50"'; }
      $p_hht->{$fileportname} .= sprintf(qq(    <th%s>%s</th>\n), $cw, $p_table_format->{$position}{'hdr'}); 
    }
    $p_hht->{$fileportname} .= "  </tr>\n";
    $p_hht->{$fileportname} .= qq(  </thead>\n);

    ### Build, prepare and execute the main query.
    if ($hash_params{'sold'}) {
      $table = 'transaction_list';
      $sorter = 'pctgain';
      $query = sprintf("SELECT %s from %s where ((%s = '%s') && (closed)) order by %s %s", $table_format_fields_string, $table, 'fileportname', $fileportname, $sorter, $hash_params{'sortdir'});
    } else {
      $table = 'transaction_report';
      $sorter = $hash_params{'sort'};
      $query = sprintf("SELECT %s from %s where %s = '%s' order by %s %s", $table_format_fields_string, $table, 'fileportname', $fileportname, $sorter, $hash_params{'sortdir'});
    }
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";

    $p_hht->{$fileportname} .= qq(  <tbody>\n);
    ### Loop over each db entry.
    while ($p_dbrow = $sth->fetchrow_hashref()) {
      $symbol = $p_dbrow->{'symbol'};
      $p_hht->{$fileportname} .= qq(  <tr>\n);
      my $r = -1;
      foreach my $position (@{$p_table_format_keys}) {
        $r++;
        if (($handheld_result) && (! $p_table_format->{$position}{'handheld'})) { next; }
        if (($p_table_format->{$position}{'fld'} eq 'name') && (! $hash_params{'showname'})) { next; }
        if (($p_table_format->{$position}{'fld'} eq 'sector') && (! $hash_params{'showsector'})) { next; }
        if ($p_table_format->{$position}{'fld'} eq 'name') {  # Remove single quotes and change ampersands
          $p_dbrow->{$p_table_format->{$position}{'fld'}} =~ s/'//g;
          $p_dbrow->{$p_table_format->{$position}{'fld'}} =~ s/&/&amp;/g;
        }
        if (! $p_table_format->{$position}{'style'}) { 
          ### Skip any fields that have style=0
          next; 
        } elsif ($p_table_format->{$position}{'style'} eq 'normal') {
          ### Normal style, one print field, may have custom bgcolor.
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, $p_dbrow->{$p_table_format->{$position}{'fld'}}); 
        } elsif ($p_table_format->{$position}{'style'} eq 'two_fmt') {
          ### 2FMT style, one print field, 2 possible formats.
          if ($p_dbrow->{$p_table_format->{$position}{'fld'}} =~ /\.0000$/) {
            $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, $p_dbrow->{$p_table_format->{$position}{'fld'}}); 
          } else {
            $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt2'}, $p_dbrow->{$p_table_format->{$position}{'fld'}}); 
          }
        } elsif ($p_table_format->{$position}{'style'} eq 'sp_links') {
          ### Special style, multiple links/images in the table cell.
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, make_link_string('yahoo_key_stats', $symbol), make_link_string('marketwatch_chart', $symbol), make_link_string('yahoo_basic_chart', $symbol)); 
        } elsif ($p_table_format->{$position}{'style'} eq 'sp_label') {
          ### Special style, link to keystats based on symbol.
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, make_link_string('yahoo_quote', $symbol), $p_dbrow->{$p_table_format->{$position}{'fld'}});
        } elsif ($p_table_format->{$position}{'style'} eq 'sp_float') {
          ### Special style, bgcolor, print field
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, calc_bgcolor($p_dbrow->{$p_table_format->{$position}{'bg'}}, $p_table_format->{$position}{'bgmin'}, $p_table_format->{$position}{'bgmax'}), $p_dbrow->{$p_table_format->{$position}{'fld'}}); 
        } elsif ($p_table_format->{$position}{'style'} eq 'sp_bar') {
          ### Special style, horizontal bar to represent position between lo/hi
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, sprintf("/pics/%s.gif", $port_color), $p_dbrow->{$p_table_format->{$position}{'fld'}}/2); 
        } elsif ($p_table_format->{$position}{'style'} eq 'sp_cagr') {
          ### Special handling for CAGR
          if ($p_dbrow->{$p_table_format->{$position}{'fld'}} > 999.95) {
            $cagr = '> 999.9%';
          } else {
            $cagr = sprintf($p_table_format->{$position}{'fld_fmt'}, $p_dbrow->{$p_table_format->{$position}{'fld'}});
          }
          $p_hht->{$fileportname} .= sprintf(qq(    <td align="right">%s</td>\n), $cagr); 
        } elsif ($p_table_format->{$position}{'style'} eq 'magnitude') {
          ### Special handling for magnitude
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, magnitude_string($p_dbrow->{$p_table_format->{$position}{'fld'}})); 
        } elsif ($p_table_format->{$position}{'style'} eq 'exdiv') {
          ### Special handling for ex_div display
          $p_hht->{$fileportname} .= sprintf($p_table_format->{$position}{'fld_fmt'}, change_exdiv($p_dbrow->{$p_table_format->{$position}{'fld'}})); 
        }
      }
      $p_hht->{$fileportname} .= "  </tr>\n";
    }
    $p_hht->{$fileportname} .= qq(  </tbody>\n);

    if (! $hash_params{'sold'}) {
      $p_hht->{$fileportname} .= qq(  <tfoot>\n);
      ### Add a cash row to TABLE
      $p_hht->{$fileportname} .= qq(  <tr>\n);
      foreach my $position (@{$p_table_format_keys}) {
        if (($handheld_result) && (! $p_table_format->{$position}{'handheld'})) { next; }
        if (($p_table_format->{$position}{'fld'} eq 'name') && (! $hash_params{'showname'})) { next; }
        if (($p_table_format->{$position}{'fld'} eq 'sector') && (! $hash_params{'showsector'})) { next; }
        if ($p_table_format->{$position}{'fld'} eq 'symbol') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell">CASH</td>\n)); } 
        elsif ($p_table_format->{$position}{'fld'} eq 'name') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell">Uninvested cash</td>\n)); } 
        elsif ($p_table_format->{$position}{'fld'} eq 'sector') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell">Cash equivalents</td>\n)); } 
        elsif ($p_table_format->{$position}{'fld'} eq 'shares') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell" align="right">%.2f</td>\n), $hash_port_param{$fileportname}{'cash'}); }
        elsif ($p_table_format->{$position}{'fld'} eq 'purchase_price') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell" align="right">1.00</td>\n)); } 
        elsif ($p_table_format->{$position}{'fld'} eq 'label') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell" align="center">CASH</td>\n)); } 
        elsif ($p_table_format->{$position}{'fld'} eq 'market_value') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell" align="right">%.2f</td>\n), $hash_port_param{$fileportname}{'cash'}); }
        elsif ($p_table_format->{$position}{'fld'} eq 'pct_port') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell" align="right">%.2f%%</td>\n), (100.0 - $hash_port_param{$fileportname}{'pct_invested'})); }
        elsif ($p_table_format->{$position}{'fld'} eq 'basis') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="cashcell" align="right">%.2f</td>\n), $hash_port_param{$fileportname}{'cash'}); }
        else { $p_hht->{$fileportname} .= qq(    <td class="cashcell"></td>\n); } 
      }
      $p_hht->{$fileportname} .= qq(  </tr>\n);
      ### Add Summary row to TABLE
      $color_pct_daygain = calc_bgcolor($hash_port_param{$fileportname}{'pct_daygain'}, 0.1, 10.0);
      $color_pct_gain    = calc_bgcolor($hash_port_param{$fileportname}{'pct_gain'}, 1.0, 50.0);
      $p_hht->{$fileportname} .= qq(  <tr>\n);
      foreach my $position (@{$p_table_format_keys}) {
        if (($handheld_result) && (! $p_table_format->{$position}{'handheld'})) { next; }
        if (($p_table_format->{$position}{'fld'} eq 'name') && (! $hash_params{'showname'})) { next; }
        if (($p_table_format->{$position}{'fld'} eq 'sector') && (! $hash_params{'showsector'})) { next; }
        if ($p_table_format->{$position}{'fld'} eq 'symbol') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="totalcell">TOTAL</td>\n)); }
        elsif ($p_table_format->{$position}{'fld'} eq 'label') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="totalcell" align="center">TOTAL</td>\n)); }
        elsif ($p_table_format->{$position}{'fld'} eq 'pct_chg') { $p_hht->{$fileportname} .= sprintf(qq(    <td align="right" bgcolor="%s">%.2f%%</td>\n), $color_pct_daygain, $hash_port_param{$fileportname}{'pct_daygain'}); }
        elsif ($p_table_format->{$position}{'fld'} eq 'daygain') { $p_hht->{$fileportname} .= sprintf(qq(    <td align="right" bgcolor="%s">%.2f</td>\n),   $color_pct_daygain, $hash_port_param{$fileportname}{'daygain'}); }
        elsif ($p_table_format->{$position}{'fld'} eq 'market_value') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="totalcell" align="right">%.2f</td>\n), ($hash_port_param{$fileportname}{'invested_total'} + $hash_port_param{$fileportname}{'cash'})); }
        elsif ($p_table_format->{$position}{'fld'} eq 'pct_gain') { $p_hht->{$fileportname} .= sprintf(qq(    <td align="right" bgcolor="%s">%.2f%%</td>\n), $color_pct_gain, $hash_port_param{$fileportname}{'pct_gain'}); }
        elsif ($p_table_format->{$position}{'fld'} eq 'gain') { $p_hht->{$fileportname} .= sprintf(qq(    <td align="right" bgcolor="%s">%.2f</td>\n),   $color_pct_gain, $hash_port_param{$fileportname}{'gain'}); }
        elsif ($p_table_format->{$position}{'fld'} eq 'pct_port') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="totalcell" align="right">%.2f%%</td>\n), 100.0); }
        elsif ($p_table_format->{$position}{'fld'} eq 'basis') { $p_hht->{$fileportname} .= sprintf(qq(    <td class="totalcell" align="right">%.2f</td>\n), $hash_port_param{$fileportname}{'basis'}); }
        else { $p_hht->{$fileportname} .= qq(    <td class="totalcell"></td>\n); } 
      }
      $p_hht->{$fileportname} .= qq(  </tr>\n);
      $p_hht->{$fileportname} .= qq(  </tfoot>\n);
    }

    ### End TABLE html
    $p_hht->{$fileportname} .= qq(</table>\n);
    $p_hht->{$fileportname} .= qq(</td></tr>\n);
    $p_hht->{$fileportname} .= qq(</table>\n);

    $p++; ### Used to index into arrays that have entries per port.
  }

  return($p_hht);
}

######################################################################################################
#################################### MAIN PROGRAM ####################################################
######################################################################################################

our $p_hash_html_tables;
our $fileportname;
our $html_ticker_table;
our $html_summary_table;

our $chart_start;
our $chart_end;
our $jan1_secs;
our $handheld_env = $FALSE;

### Check if handheld.
if (($ENV{'HTTP_USER_AGENT'} =~ /iPhone/) || ($ENV{'HTTP_USER_AGENT'} =~ /SAMSUNG-SGH/) || ($ENV{'HTTP_USER_AGENT'} =~ /Android.*Nexus 5/)) { 
  $handheld_env = $TRUE; 
}
$handheld_agent = ($handheld_env) ? 1 : 0;

### Connect to database
$dbh = DBI->connect('dbi:mysql:track_port', 'blreams') or die "ERROR: Connection error: $DBI::errstr\n";

### Build %hash_list_ports from DB.
get_all_ports(\%hash_list_ports, \%hash_hash_ports);

### Untaint and process parameters.
untaint_params(\$method_param, \$viewname_param, \$combined_param, \$showname_param, \$showsector_param, \$handheld_param, \$sort_param, \$sold_param);
process_params($method_param, $viewname_param, $combined_param, $showname_param, $showsector_param, $handheld_param, $sort_param, $sold_param);

### Use $handheld_param if force as _GET input, otherwise leave auto-detect value
if (! defined($handheld_param)) { $handheld_result = $handheld_agent; } else { $handheld_result = $handheld_param; }

### Get table_format from DB
($p_table_format, $p_table_format_keys) = get_table_format();

### Calculate some dates.
$chart_end = strftime("%m/%d/%Y", localtime(parsedate('now')));
$jan1_secs = parsedate('now') - parsedate("01/01/" . strftime("%Y", localtime(parsedate('now'))));
if ($jan1_secs < (60 * 60 * 24 * 21)) {
  $chart_start = strftime("%m/%d/%Y", localtime(parsedate('now - 1 year')));
} else {
  $chart_start = '12/31/' . strftime("%Y", localtime(parsedate('last year')));
}

### Do a Whee Doggie check
$whee_doggie_value = whee_doggie_check();

### Call functions to build the html tables
$html_ticker_table = get_ticker_table();
$html_summary_table = get_summary_table();
$p_hash_html_tables = get_main_tables();

### The rest is HTML generation.
print $q->header( 'text/html' );
html_header;
printf(qq(<table class="top_tab"><tr>\n));
printf(qq(<td>\n));
printf("%s", $html_ticker_table);
if (! $handheld_result) {
  printf(qq(</td><td>\n));
} else {
  printf(qq(</td></tr><tr><td>\n));
}
printf("%s", $html_summary_table);
if (! $handheld_result) {
  printf(qq(</td><td>\n));
  printf(qq(  <a href="port_pie.cgi?%s&amp;combined=%s&amp;geom=1x1&amp;plot=html">\n), $hash_params{'raw_ports'}, ($hash_params{'combined'}?'TRUE':'FALSE'));
  printf(qq(    <img src="port_pie.cgi?%s&amp;combined=%s&amp;geom=%s&amp;plot=summary" alt=""/>\n), $hash_params{'raw_ports'}, ($hash_params{'combined'}?'TRUE':'FALSE'), get_geom());
  printf(qq(  </a>\n));
}
printf(qq(</td></tr></table>\n));
foreach $fileportname (@{$hash_params{'ports'}}) {
  printf("%s", $p_hash_html_tables->{$fileportname});
}
info_table;
require "../cgi-bin/pagecounter.cgi";
html_footer;

