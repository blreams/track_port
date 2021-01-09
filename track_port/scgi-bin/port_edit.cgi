#!/usr/bin/perl -T
# Copyright 2009 BLR.
# All rights reserved.
# This is unpublished, confidential BLR proprietary
# information.  Do not reproduce without written permission.
#
# file:         port_edit.cgi
#
# description:
#
# Modification History
#
# when      ver   who       what
# --------  ---   --------  -----------------------------------------
# 02/04/11  1.0   blreams   initial
# 02/04/13  2.0   blreams   added ability to handle commissions on new stock.
# 02/10/13  2.1   blreams   major overhaul to new_transaction form and submit.
# 02/21/13  2.2   blreams   changed "sell" to "close" terminology.
# 02/23/13  2.3   blreams   minor fix for calculations involving commissions.
# 02/23/13  2.4   blreams   added total column for show_transactions.
# 02/25/13  2.5   blreams   fix for calc_current_cash that includes options.
# 02/26/13  2.6   blreams   can close short positions.
# 04/09/13  2.7   blreams   use abs(close_price) when calculating from short shares and tablesorter changes.
# 04/14/13  2.8   blreams   added header row to default form for Edit Port section.
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
our $script_ver = '2.8';
our $min_args = 0;
our $max_args = 2;

sub usage {
  printf(STDERR "\n");
  printf(STDERR "USAGE: $script_name  [--help] [--version] [--debug] [--verbose] \n");
  printf(STDERR "USAGE:   [--help] - help information\n");
  printf(STDERR "USAGE:   [--version] - version information\n");
  printf(STDERR "USAGE:   [--debug] - print mysql statements that would be executed\n");
  printf(STDERR "USAGE:   [--verbose] - print verbose messages\n");
  printf(STDERR "\n");
}

#-----------------------------------------------------------------------------
# Assign constants
#-----------------------------------------------------------------------------
Readonly our $FALSE => 0;
Readonly our $TRUE  => 1;

#-----------------------------------------------------------------------------
# Declarations
#-----------------------------------------------------------------------------
our $DBDATEFMT = "%Y-%m-%d";   # Use this w/ strftime to get a date in db format.
our $p_list_fields;            # Will point to a list of fields for transaction_list table.
our %hash_fields_index;        # Allows converting field name to index.
our $msg;                      # Used for returning error messages.
our $today = strftime("%m/%d/%Y", localtime(parsedate("now")));

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
# $q->param(action       => ('submit_close_transaction_by_id'));
# $q->param(id           => ('7836'));
# $q->param(symbol       => (''));
# $q->param(sector       => (''));
# $q->param(position     => ('long'));
# $q->param(descriptor   => ('call'));
# $q->param(shares       => (''));
# $q->param(open_price   => (''));
# $q->param(commission   => (''));
# $q->param(net_total    => (''));
# $q->param(open_date    => (''));
# $q->param(expiration   => (''));
# $q->param(strike       => (''));

# $q->param(action     => ('submit_split'));
# $q->param(symbol     => ('INTC'));
# $q->param(splita     => ('2'));
# $q->param(splitb     => ('1'));
# $q->param(splitdate  => ('11/27/2011'));

  $q->param(file  => ('spp', 'port'));
# $q->param(action => ('edit_transaction_by_id_form')); $q->param('id' => ('4'));
# $q->param(action => ('show_transactions')); $q->param('fileportname' => ('port:fluffgazer'));
# $q->param(action => ('submit_new_port')); $q->param(file => ('gem_watch')); $q->param(port => ('practice')); $q->param(initial_cash => ('0.00'));

# $q->param(action=>('submit_new_transaction'));$q->param(fileportname=>('practice:dummy'));
# $q->param(symbol=>('goog'));$q->param(sector=>('aaa'));$q->param(position=>('long'));$q->param(descriptor=>('stock'));
# $q->param(shares=>('123.45'));$q->param(open_price=>('1750.75'));$q->param(open_date=>('yesterday'));

$q->param(action=>('submit_new_cash_transaction'));$q->param(fileportname=>('practice:dummy'));
$q->param(position=>('cash'));$q->param(descriptor=>('intermediate'));$q->param(open_price=>('25.00'));
$q->param(open_date=>('yesterday'));$q->param(sector=>('dividend'));$q->param(symbol=>('INTC'));

# $q->param(action=>('delete_transaction_by_id'));$q->param(id=>('1280'));
# $q->param(action=>('submit_edit_cash_by_id'));$q->param(id=>('1559'));$q->param(fileportname=>('gem:gem_port'));$q->param(symbol=>('CASH'));$q->param(sector=>('interest'));$q->param(position=>('cash'));$q->param(descriptor=>('intermediate'));$q->param(shares=>('0.0000'));$q->param(open_price=>('-3.7700'));$q->param(open_date=>('2009-05-28'));$q->param(closed=>('0'));$q->param(close_price=>('0.0000'));$q->param(close_date=>(''));$q->param(expiration=>(''));$q->param(strike=>('0.0000'));
}

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------
our $dbh = DBI->connect('dbi:mysql:track_port', 'blreams') or die "ERROR: Connection error: $DBI::errstr\n";

our %hash_params;

#----------------------------------------------------------------------------
# untaint_params
#   untaint $q->param and return a hash that represents all parameters.
#----------------------------------------------------------------------------
sub untaint_params {
  my ($p_hash_params) = @_;
  my @a;

  my @param_names = $q->param();

  foreach my $p (@param_names) {
    @a = $q->param($p);
    push(@{$p_hash_params->{$p}}, @a);
  }
}


#----------------------------------------------------------------------------
# calc_current_cash
#----------------------------------------------------------------------------
sub calc_current_cash($) {
  my ($fpn) = @_;
  my $query;
  my $sth;
  my @dbrow;
  my $p_querydata;
  my $current_cash;

  ### First grab the initial cash transaction for fpn.
  $query = "SELECT open_price FROM transaction_list WHERE ((position = 'cash') && (descriptor = 'initial') && (fileportname = '$fpn'))";
  $p_querydata = $dbh->selectrow_arrayref($query);
  $current_cash = $p_querydata->[0];
  ### Next get all the long, stock, not open positions and reduce current_cash by each.
  $query = "SELECT shares,open_price FROM transaction_list WHERE ((position = 'long') && (descriptor in ('stock', 'call', 'put')) && (NOT closed) && (fileportname = '$fpn'))";
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";
  while (@dbrow = $sth->fetchrow_array()) { $current_cash -= $dbrow[0] * $dbrow[1]; }
  ### Next get all the cash, intermediate transactions and add to current_cash.
  $query = "SELECT open_price FROM transaction_list WHERE ((position = 'cash') && (descriptor = 'intermediate') && (fileportname = '$fpn'))";
  $p_querydata = $dbh->selectcol_arrayref($query);
  for (my $i = 0; $i <= $#{$p_querydata}; $i++) { $current_cash += $p_querydata->[$i]; }
  ### Next get all the long, stock, not open positions and reduce current_cash by each.
  $query = "SELECT shares,open_price,close_price FROM transaction_list WHERE ((position = 'long') && (descriptor in ('stock', 'call', 'put')) && (closed) && (fileportname = '$fpn'))";
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr";
  while (@dbrow = $sth->fetchrow_array()) { $current_cash += $dbrow[0] * ($dbrow[2] - $dbrow[1]); }

  return($current_cash);
}

#----------------------------------------------------------------------------
# default_form
#----------------------------------------------------------------------------
sub default_form(;$) {
  my ($msg) = @_;
  my $fileportname;
  my $filename;
  my $portname;
  my $query;
  my $p_list_ports;
  my %hash_file_port_lists = ();

  if ($hash_params{'file'}) {
    foreach my $f (@{$hash_params{'file'}}) {
      if (length($f) > 0) { $query .= "(fileportname REGEXP '^$f:') || "; }
    }
    $query = substr($query, 0, -4) . ')';
    if (length($query) > 2) { $query = ' WHERE (' . $query; } else { $query = ''; }
  }
  $query = 'SELECT fileportname FROM transaction_list ' . $query;
  $query .= ' GROUP BY fileportname';

  $p_list_ports = $dbh->selectcol_arrayref($query);

  # Create a hash of lists - index=file, value=list of ports
  foreach $fileportname (@{$p_list_ports}) {
    ($filename, $portname) = split(/:/, $fileportname);
    push(@{$hash_file_port_lists{$filename}}, $portname);
  }

  printf(qq(    <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(      <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><th colspan="%s">Edit Port:</th></tr>\n), scalar(keys(%hash_file_port_lists)));
  printf(qq(        <tr>\n));
  foreach $filename (sort(keys(%hash_file_port_lists))) {
    printf(qq(          <td valign="top">%s:<br />\n), $filename);
    foreach $portname (sort(@{$hash_file_port_lists{$filename}})) {
      printf(qq(            <input type="radio" name="fileportname" value="%s"/>%s<br />\n), ($filename . ':' . $portname), $portname);
    }
  }
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(        <tr><td colspan="%s">\n), scalar(keys(%hash_file_port_lists)));
  printf(qq(          <input type="submit" value="Submit"/>\n));
  printf(qq(          <input type="reset" value="Reset"/>\n));
  printf(qq(        </td></tr>\n));
  printf(qq(      </table>\n));
  printf(qq(    </form>\n));

  my $file = ($hash_params{'file'}[0]) ? $hash_params{'file'}[0] : '';
  my $port = ($hash_params{'port'}[0]) ? $hash_params{'port'}[0] : '';
  my $initial_cash = ($hash_params{'initial_cash'}[0]) ? $hash_params{'initial_cash'}[0] : '0.00';

  printf(qq(    <form name="submit_new_port" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(      <input type="hidden" name="action" value="submit_new_port"/>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>\n));
  printf(qq(          <table border="0">\n));
  printf(qq(            <tr><th colspan="2">Create New Port:</th></tr>\n));
  printf(qq(            <tr><td>File:</td><td><input type="text" name="file" value="%s"/></td></tr>\n), $file);
  printf(qq(            <tr><td>Port:</td><td><input type="text" name="port" value="%s"/></td></tr>\n), $port);
  printf(qq(            <tr><td>Initial Cash:</td><td><input type="text" name="initial_cash" value="%s"/></td></tr>\n), $initial_cash);
  printf(qq(            <tr><td><input type="submit" value="New"/></td></tr>\n));
  printf(qq(          </table>\n));
  printf(qq(        </td></tr>\n));
  printf(qq(      </table>\n));
  printf(qq(    </form>\n));
  printf(qq(    <form name="submit_split" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(      <input type="hidden" name="action" value="submit_split"/>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>\n));
  printf(qq(          <table border="0">\n));
  printf(qq(            <tr><th colspan="4">Enter Stock Split:</th></tr>\n));
  printf(qq(            <tr><td>Symbol:</td><td colspan="3"><input type="text" name="symbol" value="%s" size="6"/></td></tr>\n), '');
  printf(qq(            <tr><td>Split:</td><td><input type="text" name="splita" value="%s" size="4"/></td><td>:</td><td><input type="text" name="splitb" value="%s" size="4"/></td></tr>\n), '','');
  printf(qq(            <tr><td>Date:</td><td colspan="3"><input type="text" name="splitdate" value="%s"/></td></tr>\n), $today);
  printf(qq(            <tr><td><input type="submit" value="Split"/></td></tr>\n));
  printf(qq(          </table>\n));
  printf(qq(        </td></tr>\n));
  printf(qq(      </table>\n));
  printf(qq(    </form>\n));
  if ($msg) {
    printf(qq(    <table><tr><td>%s</td></tr></table>\n), $msg);
  }
}


#----------------------------------------------------------------------------
# show_transactions_form
#----------------------------------------------------------------------------
sub show_transactions_form {
  my ($portname) = @_;
  my ($fname, $pname) = split(/:/, $portname);

  my %skip_fields = ( 'id' => 1, 'fileportname' => 1, 'closed' => 1, 'close_price' => 1, 'close_date' => 1, 'expiration' => 1, 'strike' => 1 );
  my $torder = ($hash_params{torder}[0]) ? $hash_params{torder}[0] : 'open_date';
  my $tdir = ($hash_params{tdir}[0] eq 'ASC') ? 'DESC' : 'ASC';
  my $corder = ($hash_params{corder}[0]) ? $hash_params{corder}[0] : 'open_date';
  my $cdir = ($hash_params{cdir}[0] eq 'ASC') ? 'DESC' : 'ASC';
  my $query = sprintf("SELECT * FROM transaction_list WHERE ((fileportname = '%s') && (position != 'cash') && (NOT closed)) ORDER by %s %s,symbol", $portname, $torder, $tdir);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";

  ### Start a table to put transactions and cash side-by-side.
  printf(qq(    <table border="0"><tr valign="top"><td>\n));

  ### Generate table w/ open transactions
  ### Header for table
  printf(qq(      <table class="opens_title_tab" border="0">\n));
  printf(qq(      <tr>\n));
  printf(qq(      <td class="table_title">Open Transactions List [%s]</td>\n), $pname);
  printf(qq(      <td>\n));
  printf(qq(        <form name="new_stock_transaction_using_insert" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(        <table border="0">\n));
  printf(qq(        <tr><td>\n));

  ### Form with Open Position button and radio selector buttons.
  printf(qq(          <input type="hidden" name="action" value="new_transaction"/>\n));
  printf(qq(          <input type="hidden" name="fileportname" value="%s"/>\n), $hash_params{'fileportname'}[0]);
  printf(qq(          <input type="hidden" name="position" value="long"/>\n));
  printf(qq(          <input type="hidden" name="descriptor" value="stock"/>\n));
  printf(qq(          <div class="ot_left">\n));
  printf(qq(          <input type="radio" name="security_type" value="stock" checked />Stock/MFund<br />\n));
  printf(qq(          <input type="radio" name="security_type" value="call"/>Call Option<br />\n));
  printf(qq(          <input type="radio" name="security_type" value="put"/>Put Option<br />\n));
  printf(qq(          </div>\n));
  printf(qq(        </td><td>\n));
  printf(qq(          <div class="ot_left">\n));
  printf(qq(          <input type="radio" name="buy_type" value="long" checked />Buy to open (long)<br />\n));
  printf(qq(          <input type="radio" name="buy_type" value="short"/>Sell to open (short)<br />\n));
  printf(qq(          </div>\n));
  printf(qq(          <input type="submit" value="Open Position"/>\n));
  printf(qq(        </td></tr>\n));
  printf(qq(        </table>\n));
  printf(qq(        </form>\n));
  printf(qq(      </td>\n));
  printf(qq(      </tr>));
  printf(qq(      </table>\n));

  ### Generate table w/ open non-cash transactions.
  printf(qq(      <table class="opens_tab" border="0">\n));
  printf(qq(      <thead>\n));
  printf(qq(      <tr>\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    if ($skip_fields{$p_list_fields->[$i]}) { next; }
    printf(qq(      <th>%s</th>\n), $p_list_fields->[$i]);
  }
  printf(qq(      <th>%s</th>\n), 'total');
  printf(qq(      <th>%s</th>\n), 'actions');
  printf(qq(      </tr>\n));
  printf(qq(      </thead>\n));

  my $r = 0;

  printf(qq(      <tbody>\n));
  while (my $p_dbrow = $sth->fetchrow_arrayref()) {
    printf(qq(        <tr>\n));
    for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
      if ($skip_fields{$p_list_fields->[$i]}) { next; }
      printf(qq(        <td>%s</td>\n), $p_dbrow->[$i]);
    }
    printf(qq(        <td>%.2f</td>\n), ($p_dbrow->[$hash_fields_index{shares}] * $p_dbrow->[$hash_fields_index{open_price}]));
    printf(qq(        <td>\n));
    ### Close button
    printf(qq(          <div style="float:left;">\n));
    printf(qq(            <form name="%s" action="/scgi-bin/port_edit.cgi" method="get">\n), ('close_transaction_by_id' . $r));
    printf(qq(            <input type="hidden" name="action" value="close_transaction_by_id"/>\n));
    printf(qq(            <input type="hidden" name="id" value="%d"/>\n), $p_dbrow->[0]);
    printf(qq(            <input type="submit" value="CLOSE"/>\n));
    printf(qq(            </form>\n));
    printf(qq(          </div>\n));
    ### Edit button
    printf(qq(          <div style="float:left;">\n));
    printf(qq(            <form name="%s" action="/scgi-bin/port_edit.cgi" method="get">\n), ('edit_transaction_by_id' . $r));
    printf(qq(            <input type="hidden" name="action" value="edit_transaction_by_id"/>\n));
    printf(qq(            <input type="hidden" name="id" value="%d"/>\n), $p_dbrow->[0]);
    printf(qq(            <input type="submit" value="EDIT"/>\n));
    printf(qq(            </form>\n));
    printf(qq(          </div>\n));
    ### Delete button
    printf(qq(          <div style="float:left;">\n));
    printf(qq(            <form name="%s" action="/scgi-bin/port_edit.cgi" method="get">\n), ('delete_transaction_by_id' . $r));
    printf(qq(            <input type="hidden" name="action" value="delete_transaction_by_id"/>\n));
    printf(qq(            <input type="hidden" name="id" value="%d"/>\n), $p_dbrow->[0]);
    printf(qq(            <input type="submit" value="DELETE"/>\n));
    printf(qq(            </form>\n));
    printf(qq(          </div>\n));
    printf(qq(          </td>\n));
    printf(qq(        </tr>\n));

    $r++;
  }
  printf(qq(      </tbody>\n));
  printf(qq(      </table>\n));      # opens_tab

  %skip_fields = ( 'id'=>1, 'fileportname'=>1, 'closed'=>1, 'close_price'=>1, 'close_date'=>1, 'expiration'=>1, 'strike'=>1 );
  $query = sprintf("SELECT * FROM transaction_list WHERE ((fileportname = '%s') && (position = 'cash')) ORDER by %s %s,descriptor", $portname, $corder, $cdir);
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";

  printf(qq(    </td><td>\n));

  ### Generate table w/ cash transactions
  ### Header for table
  printf(qq(      <table class="cash_title_tab" border="0">\n));
  printf(qq(      <tr>\n));
  printf(qq(      <td class="table_title">Cash Transactions List [%s]</td>\n), $pname);
  printf(qq(      <td>\n));
  printf(qq(        <table border="0">\n));
  printf(qq(        <tr><td>\n));
  ### New Intermediate Cash button
  printf(qq(          <form name="new_transaction_using_insert0" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(          <input type="hidden" name="action" value="new_cash_transaction"/>\n));
  printf(qq(          <input type="hidden" name="fileportname" value="%s"/>\n), $hash_params{'fileportname'}[0]);
  printf(qq(          <input type="hidden" name="position" value="cash"/>\n));
  printf(qq(          <input type="hidden" name="descriptor" value="intermediate"/>\n));
  printf(qq(          <input type="submit" value="Add Cash"/>\n));
  printf(qq(          </form>\n));
  printf(qq(        </td><td>\n));
  ### New Final Cash button
  printf(qq(          <form name="new_transaction_using_insert1" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(          <input type="hidden" name="action" value="new_cash_transaction"/>\n));
  printf(qq(          <input type="hidden" name="fileportname" value="%s"/>\n), $hash_params{'fileportname'}[0]);
  printf(qq(          <input type="hidden" name="position" value="cash"/>\n));
  printf(qq(          <input type="hidden" name="descriptor" value="final"/>\n));
  printf(qq(          <input type="submit" value="Final Cash"/>\n));
  printf(qq(          </form>\n));
  printf(qq(        </td></tr>\n));
  printf(qq(        </table>\n));
  printf(qq(      </td>\n));
  printf(qq(      </tr>\n));
  printf(qq(      </table>\n));

  ### Generate table w/ only cash transactions.
  printf(qq(      <table class="cash_tab" border="0">\n));
  printf(qq(      <thead>\n));
  printf(qq(      <tr>\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    if ($skip_fields{$p_list_fields->[$i]}) { next; }
    printf(qq(      <th>%s</th>\n), $p_list_fields->[$i]);
  }
  printf(qq(      <th>%s</th>\n), 'actions');
  printf(qq(      </tr>\n));
  printf(qq(      </thead>\n));

  $r = 0;

  printf(qq(      <tbody>\n));
  while (my $p_dbrow = $sth->fetchrow_arrayref()) {
    printf(qq(      <tr>\n));
    for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
      if ($skip_fields{$p_list_fields->[$i]}) { next; }
      printf(qq(      <td>%s</td>\n), $p_dbrow->[$i]);
    }
    printf(qq(      <td>\n));
    printf(qq(        <div style="float:left;">\n));
    printf(qq(          <form name="%s" action="/scgi-bin/port_edit.cgi" method="get">\n), ('edit_cash_by_id' . $r));
    printf(qq(          <input type="hidden" name="action" value="edit_cash_by_id"/>\n));
    printf(qq(          <input type="hidden" name="id" value="%d"/>\n), $p_dbrow->[0]);
    printf(qq(          <input type="submit" value="EDIT"/>\n));
    printf(qq(          </form>\n));
    printf(qq(        </div>\n));
    ### Delete button
    printf(qq(        <div style="float:left;">\n));
    printf(qq(          <form name="%s" action="/scgi-bin/port_edit.cgi" method="get">\n), ('delete_cash_by_id' . $r));
    printf(qq(          <input type="hidden" name="action" value="delete_transaction_by_id"/>\n));
    printf(qq(          <input type="hidden" name="id" value="%d"/>\n), $p_dbrow->[0]);
    printf(qq(          <input type="submit" value="DELETE"/>\n));
    printf(qq(          </form>\n));
    printf(qq(        </div>\n));
    printf(qq(      </td>\n));
    printf(qq(      </tr>\n));
    
    $r++;
  }

  printf(qq(      </tbody>\n));
  printf(qq(      </table>\n));
  printf(qq(    </td>\n));
  printf(qq(    </tr>\n));
  printf(qq(    </table>\n));
}

#----------------------------------------------------------------------------
# submit_new_port
#----------------------------------------------------------------------------
sub submit_new_port {
  my $errormsg = '';
  my $fpn;
  my $query;
  my $p_junk;
  my $sth;

  if (! ($hash_params{'file'}[0] =~ /^\w[-\w]*$/)) {
    $errormsg .= sprintf("Parameter [file=%s], non-conforming string.  ", $hash_params{'file'}[0]);
  }
  if (length($hash_params{'file'}[0]) > 128) {
    $errormsg .= sprintf("Parameter [file=%s] is too long (limit 128 characters).  ", $hash_params{'file'}[0]);
  }
  if (! ($hash_params{'port'}[0] =~ /^\w[-\w]*$/)) {
    $errormsg .= sprintf("Parameter [port=%s], non-conforming string.  ", $hash_params{'port'}[0]);
  }
  if (length($hash_params{'port'}[0]) > 128) {
    $errormsg .= sprintf("Parameter [port=%s] is too long (limit 128 characters).  ", $hash_params{'port'}[0]);
  }
  $hash_params{'initial_cash'}[0] = sprintf("%.2f", $hash_params{'initial_cash'}[0]);

  $fpn = sprintf("%s:%s", $hash_params{'file'}[0], $hash_params{'port'}[0]);
  $query = sprintf("SELECT fileportname FROM transaction_list WHERE (fileportname = '%s')", $fpn);
  $p_junk = $dbh->selectcol_arrayref($query);
  if (scalar(@{$p_junk}) >= 1) { $errormsg .= sprintf("Port [%s] already exists.  ", $fpn); }

  if ($errormsg) { return($errormsg); }

  $query = sprintf("INSERT INTO transaction_list SET fileportname='%s',position='cash',descriptor='initial',open_price='%s'", $fpn, $hash_params{'initial_cash'}[0]);

  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  }

  $errormsg = sprintf("Port [%s] successfully created.", $fpn);
  return($errormsg);
}

#----------------------------------------------------------------------------
# submit_split
#----------------------------------------------------------------------------
sub submit_split {
  my $errormsg = '';
  my $query;
  my $sth;
  my $p_describe;
  my $p_splits;
  my %tl_fields;
  my $i;
  my $j;
  my $splitdate_secs = parsedate($hash_params{'splitdate'}[0]);

  if (! ($hash_params{'symbol'}[0] =~ /^\w+$/)) {
    $errormsg .= sprintf("Parameter [symbol=%s], non-conforming string.  ", $hash_params{'symbol'}[0]);
  }
  if (! ($hash_params{'splita'}[0] =~ /^\d+$/)) {
    $errormsg .= sprintf("Parameter [splita=%s], non-conforming string.  ", $hash_params{'splita'}[0]);
  }
  if (! ($hash_params{'splitb'}[0] =~ /^\d+$/)) {
    $errormsg .= sprintf("Parameter [splitb=%s], non-conforming string.  ", $hash_params{'splitb'}[0]);
  }
  $hash_params{'symbol'}[0] =~ tr/a-z/A-Z/;
  $hash_params{'splita'}[0] = sprintf("%.2f", $hash_params{'splita'}[0]);
  $hash_params{'splitb'}[0] = sprintf("%.2f", $hash_params{'splitb'}[0]);

  $query = 'DESCRIBE transaction_list';
  $p_describe = $dbh->selectcol_arrayref($query);
  for ($i = 0; $i <= $#{$p_describe}; $i++) {
    $tl_fields{$p_describe->[$i]} = $i;
  }

  $query = sprintf("SELECT * FROM transaction_list WHERE ((position = 'long') && (symbol = '%s')) order by open_date", $hash_params{'symbol'}[0]);
  $p_splits = $dbh->selectall_arrayref($query);

  printf(qq(    <table border="0" bgcolor="#865722">\n));
  printf(qq(      <tr><th colspan="%d"><font color="white">Transactions Being Split</font></th></tr>\n), scalar(@{$p_describe}));
  printf(qq(      <tr>\n));
  for ($j = 0; $j <= $#{$p_describe}; $j++) {
    printf(qq(        <th><font color="white">%s</font></th>\n), $p_describe->[$j]);
  }
  printf(qq(      </tr>\n));

  my @bcolors = ('#EDD4BA', '#DCAB74');
  my $bcolor;

  for ($i = 0; $i <= $#{$p_splits}; $i++) {
    my $tl_open_secs = parsedate($p_splits->[$i][$tl_fields{'open_date'}]);
    my $tl_close_secs = $FALSE;
    $tl_close_secs = parsedate($p_splits->[$i][$tl_fields{'close_date'}]) if ($p_splits->[$i][$tl_fields{'closed'}]);
    if ($tl_open_secs > $splitdate_secs) { next; }
    $bcolor = ($i % scalar(@bcolors));
    printf(qq(      <tr bgcolor="%s">\n), $bcolors[$bcolor]);
    for ($j = 0; $j <= $#{$p_describe}; $j++) {
      printf(qq(        <td>%s</td>\n), $p_splits->[$i][$j]);
    }
    printf(qq(      </tr>\n));
  }

  printf(qq(    </table>\n));

  if ($errormsg) { return($errormsg); }

  return($errormsg);
}

#----------------------------------------------------------------------------
# edit_transaction_by_id_form
#----------------------------------------------------------------------------
sub edit_transaction_by_id_form($;$) {
  my ($id, $msg) = @_;

  my %hidden_fields = ( 'id'=>1, 'fileportname'=>1 );
  my %noedit_fields = ( 'symbol'=>1, 'position'=>1, 'descriptor'=>1 );

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();

  my $f;
  my $value;

  printf(qq(      <table border="1">\n));
  printf(qq(      <form name="submit_edit_transaction_by_id" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(        <input type="hidden" name="action" value="submit_edit_transaction_by_id"/>\n));
  printf(qq(        <tr><th colspan="2">Edit Transaction</th></tr>\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    $f = $p_list_fields->[$i];
    if ($hidden_fields{$f}) { 
      printf(qq(          <input type="hidden" name="%s" value="%s"/>\n), $f, $p_dbrow->[$i]);
    } elsif ($noedit_fields{$f}) {
      printf(qq(          <tr><td>%s:</td>\n), $f);
      printf(qq(          <td><input type="hidden" name="%s" value="%s"/>%s</td></tr>\n), $f, $p_dbrow->[$i], $p_dbrow->[$i]);
    } else {
      $value = ($hash_params{$f}[0]) ? $hash_params{$f}[0] : $p_dbrow->[$i];
      printf(qq(          <tr><td>%s:</td>\n), $f);
      printf(qq(          <td><input type="text" name="%s" value="%s"/></td></tr>\n), $f, $value);
    }
  }
  printf(qq(          <tr><td colspan="2" align="center"><input type="submit" value="Update"/></td></tr>\n));
  printf(qq(        </form>\n));
  printf(qq(      </table>\n));
  if ($msg) {
    printf(qq(      <table>\n));
    printf(qq(      <tr><td>%s</td></tr>\n), $msg);
    printf(qq(      </table>\n));
  }
}

#----------------------------------------------------------------------------
# submit_edit_transaction_by_id
#----------------------------------------------------------------------------
sub submit_edit_transaction_by_id {
  my ($id) = @_;

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();
  my %update_fields;
  my $f;
  my $secs;
  my $errormsg = '';

  ### Determine if any fields have been changed.
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    $f = $p_list_fields->[$i];
    if ($p_dbrow->[$i] ne $hash_params{$f}[0]) {
      if (($f eq 'open_date') || ($f eq 'close_date') || ($f eq 'expiration')) {
        if (! ($secs = parsedate($hash_params{$f}[0]))) { 
          $errormsg .= sprintf("Unable to parse date [%s=%s].  ", $f, $hash_params{$f}[0]); 
        } else {
          $hash_params{$f}[0] = strftime($DBDATEFMT, localtime($secs));
        }
      } elsif (($f eq 'shares') || ($f eq 'open_price') || ($f eq 'close_price') || ($f eq 'strike')) {
        if ($hash_params{$f}[0] <= 0.0) { $errormsg .= sprintf("Field [%s=%s] must be > 0.0.  ", $f, $hash_params{$f}[0]); }
      } elsif ($f eq 'sector') {
        if (length($hash_params{$f}[0]) > 32) { $errormsg .= sprintf("Field [%s=%s] cannot exceed 32 chars.  ", $f, $hash_params{$f}[0]); }
      }
      $update_fields{$f} = $hash_params{$f}[0];
    }
  }
  if ($update_fields{'closed'}) {
    if (    ((! $hash_params{'close_price'}[0]) && (! $p_dbrow->[$hash_fields_index{'close_price'}]))
         || ((! $hash_params{'close_date'}[0])  && (! $p_dbrow->[$hash_fields_index{'close_date'}]))
       ) {
      $errormsg .= sprintf("Transaction close is incomplete.  ");
    }
  }
  if ($errormsg) { return($errormsg); }

  $query = '';
  if (%update_fields) {
    $query = 'UPDATE transaction_list SET ';
    foreach my $key (keys(%update_fields)) {
      $query .= sprintf("%s='%s',", $key, $update_fields{$key});
    }
    $query = substr($query, 0, -1) . " WHERE (id = '$id')";
  }

  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  }
  
  if (! $query) { $query = 'Nothing changed...'; }
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>%s</td></tr>\n), $query);
  printf(qq(      </table>\n));

  $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  $p_dbrow = $sth->fetchrow_arrayref();

  printf(qq(      <table border="1">\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    printf(qq(          <tr><td>%s:</td>\n), $p_list_fields->[$i]);
    printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$i]);
  }
  printf(qq(      </table>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="fileportname" value="%s"/>\n), $p_dbrow->[$hash_fields_index{'fileportname'}]);
  printf(qq(            <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(            <input type="submit" value="Show Transactions"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_ports" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="action" value="show_ports"/>\n));
  printf(qq(            <input type="submit" value="Show Ports"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(      </table>\n));
  return(0);
}

#----------------------------------------------------------------------------
# edit_cash_by_id_form
#----------------------------------------------------------------------------
sub edit_cash_by_id_form($;$) {
  my ($id, $msg) = @_;

  my %hidden_fields = ( 'id'=>1, 'fileportname'=>1, 'shares'=>1, 'closed'=>1, 'close_price'=>1, 'close_date'=>1, 'expiration'=>1, 'strike'=>1 );
  my %noedit_fields = ( 'position'=>1, 'descriptor'=>1 );

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();

  my $f;
  my $value;

  printf(qq(      <table border="1">\n));
  printf(qq(      <form name="submit_edit_cash_by_id" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(        <input type="hidden" name="action" value="submit_edit_cash_by_id"/>\n));
  printf(qq(        <tr><th colspan="2">Edit Cash</th></tr>\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    $f = $p_list_fields->[$i];
    if ($hidden_fields{$f}) { 
      printf(qq(          <input type="hidden" name="%s" value="%s"/>\n), $f, $p_dbrow->[$i]);
    } elsif ($noedit_fields{$f}) {
      printf(qq(          <tr><td>%s:</td>\n), $f);
      printf(qq(          <td><input type="hidden" name="%s" value="%s"/>%s</td></tr>\n), $f, $p_dbrow->[$i], $p_dbrow->[$i]);
    } else {
      $value = ($hash_params{$f}[0]) ? $hash_params{$f}[0] : $p_dbrow->[$i];
      printf(qq(          <tr><td>%s:</td>\n), $f);
      printf(qq(          <td><input type="text" name="%s" value="%s"/></td></tr>\n), $f, $value);
    }
  }
  printf(qq(          <tr><td colspan="2" align="center"><input type="submit" value="Update"/></td></tr>\n));
  printf(qq(        </form>\n));
  printf(qq(      </table>\n));
  if ($msg) {
    printf(qq(      <table>\n));
    printf(qq(      <tr><td>%s</td></tr>\n), $msg);
    printf(qq(      </table>\n));
  }
}

#----------------------------------------------------------------------------
# submit_edit_cash_by_id
#----------------------------------------------------------------------------
sub submit_edit_cash_by_id {
  my ($id) = @_;

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();
  my %update_fields;
  my $f;
  my $secs;
  my $errormsg = '';

  ### Determine if any fields have been changed.
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    $f = $p_list_fields->[$i];
    if ($p_dbrow->[$i] ne $hash_params{$f}[0]) {
      if (($f eq 'open_date') || ($f eq 'close_date') || ($f eq 'expiration')) {
        if (! ($secs = parsedate($hash_params{$f}[0]))) { 
          $errormsg .= sprintf("Unable to parse date [%s=%s].  ", $f, $hash_params{$f}[0]); 
        } else {
          $hash_params{$f}[0] = strftime($DBDATEFMT, localtime($secs));
        }
      } elsif ($f eq 'open_price') {
        if ($hash_params{$f}[0] !~ /^(-?\d+\.\d*)|(-?\d*\.\d+)|(-?\d+)$/) { $errormsg .= sprintf("Field [%s=%s] must be a real number.  ", $f, $hash_params{$f}[0]); }
      } elsif (($f eq 'shares') || ($f eq 'close_price') || ($f eq 'strike')) {
        if ($hash_params{$f}[0] <= 0.0) { $errormsg .= sprintf("Field [%s=%s] must be > 0.0.  ", $f, $hash_params{$f}[0]); }
      } elsif ($f eq 'sector') {
        if (length($hash_params{$f}[0]) > 32) { $errormsg .= sprintf("Field [%s=%s] cannot exceed 32 chars.  ", $f, $hash_params{$f}[0]); }
      }
      $update_fields{$f} = $hash_params{$f}[0];
    }
  }
  if ($update_fields{'closed'}) {
    if (    ((! $hash_params{'close_price'}[0]) && (! $p_dbrow->[$hash_fields_index{'close_price'}]))
         || ((! $hash_params{'close_date'}[0])  && (! $p_dbrow->[$hash_fields_index{'close_date'}]))
       ) {
      $errormsg .= sprintf("Transaction close is incomplete.  ");
    }
  }
  if ($errormsg) { return($errormsg); }

  $query = '';
  if (%update_fields) {
    $query = 'UPDATE transaction_list SET ';
    foreach my $key (keys(%update_fields)) {
      $query .= sprintf("%s='%s',", $key, $update_fields{$key});
    }
    $query = substr($query, 0, -1) . " WHERE (id = '$id')";
  }

  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  }
  
  if (! $query) { $query = 'Nothing changed...'; }
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>%s</td></tr>\n), $query);
  printf(qq(      </table>\n));

  $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  $p_dbrow = $sth->fetchrow_arrayref();

  printf(qq(      <table border="1">\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    printf(qq(          <tr><td>%s:</td>\n), $p_list_fields->[$i]);
    printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$i]);
  }
  printf(qq(      </table>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="fileportname" value="%s"/>\n), $p_dbrow->[$hash_fields_index{'fileportname'}]);
  printf(qq(            <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(            <input type="submit" value="Show Transactions"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_ports" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="action" value="show_ports"/>\n));
  printf(qq(            <input type="submit" value="Show Ports"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(      </table>\n));
  return(0);
}

#----------------------------------------------------------------------------
# close_transaction_by_id_form
#----------------------------------------------------------------------------
sub close_transaction_by_id_form($;$) {
  my ($id, $p_field_errors) = @_;

  ### Setup $p_field_errors with instructions if empty
  if (scalar(keys %{$p_field_errors}) == 0) {
    $p_field_errors->{sector}      = 'Free to change (optional)';
    $p_field_errors->{shares}      = 'Current shares is default (can do partial close)';
    $p_field_errors->{close_price} = 'Price at which position was closed (can be calculated)';
    $p_field_errors->{net_total}   = 'Net total of the transaction (optional, used for calculated fields)';
    $p_field_errors->{commission}  = 'Amount for commission (optional)';
    $p_field_errors->{close_date}  = 'Date position closed (ie. today, 3 weeks ago, 10/12/13, etc.';
  }

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();

  my %skip_fields;
  my %edit_fields = ( sector=>$p_dbrow->[$hash_fields_index{sector}], shares=>$p_dbrow->[$hash_fields_index{shares}], commission=>'', net_total=>'', close_price=>'', close_date=>'today' );
  my %fixed_fields = ( id=>$id, closed=>1 );
  my $position = $p_dbrow->[$hash_fields_index{position}];
  my $descriptor = $p_dbrow->[$hash_fields_index{descriptor}];
  my $title;

  if ($position eq 'long') {
    if ($descriptor eq 'stock') {
      %skip_fields = ( fileportname=>1, position=>1, descriptor=>1, expiration=>1, strike=>1 );
      $title = 'Close Stock';
    } elsif ($descriptor eq 'call') {
      %skip_fields = ( fileportname=>1, position=>1, descriptor=>1 );
      $title = 'Close Call Option';
    } elsif ($descriptor eq 'put') {
      %skip_fields = ( fileportname=>1, position=>1, descriptor=>1 );
      $title = 'Close Put Option';
    }
  }

  my $f;
  my $value;
  my $p_form_fields;
  my $i = 0;

  foreach my $field (@{$p_list_fields}) {
    if ($skip_fields{$field}) { next; }
    $p_form_fields->[$i++] = $field;
    if ($field eq 'close_price') {
      $p_form_fields->[$i++] = 'net_total';
      $p_form_fields->[$i++] = 'commission';
    }
  }

  printf(qq(      <table border="1">\n));
  printf(qq(      <tr><th colspan="2">%s</th></tr>\n), $title);
  printf(qq(      <form name="submit_close_transaction_by_id" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(        <input type="hidden" name="action" value="submit_close_transaction_by_id"/>\n));
  foreach $f (@{$p_form_fields}) {
    if ($skip_fields{$f}) { next; }
    if ($fixed_fields{$f}) {
      printf(qq(          <input type="hidden" name="%s" value="%s"/>\n), $f, $fixed_fields{$f});
    } elsif (defined($edit_fields{$f})) {
      $value = ($hash_params{$f}[0]) ? $hash_params{$f}[0] : $edit_fields{$f};
      printf(qq(          <tr><td>%s:</td>\n), $f);
      printf(qq(          <td><input type="text" name="%s" value="%s"/></td><td>%s</td></tr>\n), $f, $value, $p_field_errors->{$f});
    } else {
      printf(qq(          <tr><td>%s:</td>\n), $f);
      printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$hash_fields_index{$f}]);
    }
  }
  printf(qq(          <tr><td colspan="2" align="center"><input type="submit" value="Close"/></td></tr>\n));
  printf(qq(        </form>\n));
  printf(qq(      </table>\n));
  if ($p_field_errors) {
    printf(qq(      <table>\n));
    printf(qq(      <tr><td>%s</td></tr>\n), $p_field_errors);
    printf(qq(      </table>\n));
  }
}

#----------------------------------------------------------------------------
# submit_close_transaction_by_id
#----------------------------------------------------------------------------
sub submit_close_transaction_by_id {
  my ($id) = @_;

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();
  my %update_fields;
  my $secs;
  my $p_field_errors = ();
  my $key;
  my $value;
  my $short = 0;

  ### Determine if any fields have been changed.
  foreach my $f ('sector', 'shares', 'closed', 'close_price', 'close_date') {
    my $i = $hash_fields_index{$f};
    if ($p_dbrow->[$i] ne $hash_params{$f}[0]) {
      if (($f eq 'open_date') || ($f eq 'close_date') || ($f eq 'expiration')) {
        if (! ($secs = parsedate($hash_params{$f}[0]))) { 
          $p_field_errors->{$f} = sprintf("Unable to parse date [%s=%s].  ", $f, $hash_params{$f}[0]); 
        } else {
          $hash_params{$f}[0] = strftime($DBDATEFMT, localtime($secs));
        }
      } elsif ($f eq 'shares') {
        if ($p_dbrow->[$i] < 0.0) { $short = 1; }
        if ($short) {
          if ($hash_params{$f}[0] < $p_dbrow->[$i]) { $p_field_errors->{$f} = sprintf("Field [%s=%s] is not allowed...cannot buy to close more shares than position.  ", $f, $hash_params{$f}[0]); }
        } else {
          if ($hash_params{$f}[0] > $p_dbrow->[$i]) { $p_field_errors->{$f} = sprintf("Field [%s=%s] is not allowed...cannot sell to close more shares than position.  ", $f, $hash_params{$f}[0]); }
        }
        if ($hash_params{$f}[0] == 0.0) { $p_field_errors->{$f} = sprintf("Field [%s=%s] is not allowed...sold shares must be non-zero.  ", $f, $hash_params{$f}[0]); }
      } elsif ($f eq 'close_price') {
        if (! $hash_params{$f}[0]) { 
          if (! $hash_params{net_total}[0]) {
            $p_field_errors->{$f} = 'Both close_price AND net_total cannot be empty.';
            $p_field_errors->{net_total} = 'Both close_price AND net_total cannot be empty.';
          }
          ### Calculate close_price
          if (! $p_field_errors->{shares}) {
            $hash_params{$f}[0] = abs(($hash_params{net_total}[0] - $hash_params{commission}[0]) / $hash_params{shares}[0]);
          }
        } else {
          if ($hash_params{$f}[0] < 0.0) { 
            $p_field_errors->{$f} = sprintf("Field [%s=%s] must be >= 0.0.  ", $f, $hash_params{$f}[0]); 
          } else {
            $hash_params{$f}[0] -= $hash_params{commission}[0] / $hash_params{shares}[0];
          }
        }
      } elsif ($f eq 'sector') {
        if (length($hash_params{$f}[0]) > 32) { $p_field_errors->{$f} = sprintf("Field [%s=%s] cannot exceed 32 chars.  ", $f, $hash_params{$f}[0]); }
      }
      $update_fields{$f} = $hash_params{$f}[0];
    }
  }
  if ($update_fields{'closed'}) {
    if (    ((! $hash_params{'close_price'}[0]) && (! $p_dbrow->[$hash_fields_index{'close_price'}]))
         || ((! $hash_params{'close_date'}[0])  && (! $p_dbrow->[$hash_fields_index{'close_date'}]))
       ) {
      $p_field_errors->{sector} = sprintf("Transaction close is incomplete.  ");
    }
  }
  if ($p_field_errors) { return($p_field_errors); }

  ### Here is the special case where user sold less than a whole position.
  if (defined($update_fields{'shares'}) && (abs($update_fields{'shares'}) < abs($p_dbrow->[$hash_fields_index{'shares'}]))) {
    $query = 'INSERT INTO transaction_list SET ';
    foreach $key (keys(%hash_fields_index)) {
      if ($key eq 'id') { next; }
      if (defined($p_dbrow->[$hash_fields_index{$key}])) {
        $value = $p_dbrow->[$hash_fields_index{$key}];
        if ($key eq 'shares') { $value -= $update_fields{$key}; }
        $query .= sprintf("%s='%s',", $key, $value);
      }
    }
    $query = substr($query, 0, -1);

    if ($query) {
      $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
      $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
    }

    printf(qq(      <table border="1">\n));
    printf(qq(        <tr><td>%s</td></tr>\n), $query);
    printf(qq(      </table>\n));
  }
  
  $query = '';
  if (%update_fields) {
    $query = 'UPDATE transaction_list SET ';
    foreach $key (keys(%update_fields)) {
      $query .= sprintf("%s='%s',", $key, $update_fields{$key});
    }
    $query = substr($query, 0, -1) . " WHERE (id = '$id')";
  }

  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  }

  if (! $query) { $query = 'Nothing changed...'; }
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>%s</td></tr>\n), $query);
  printf(qq(      </table>\n));

  $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  $p_dbrow = $sth->fetchrow_arrayref();

  printf(qq(      <table border="1">\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    printf(qq(          <tr><td>%s:</td>\n), $p_list_fields->[$i]);
    printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$i]);
  }
  printf(qq(      </table>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="fileportname" value="%s"/>\n), $p_dbrow->[$hash_fields_index{'fileportname'}]);
  printf(qq(            <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(            <input type="submit" value="Show Transactions"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_ports" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="action" value="show_ports"/>\n));
  printf(qq(            <input type="submit" value="Show Ports"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(      </table>\n));
  return(0);
}

#----------------------------------------------------------------------------
# delete_transaction_by_id_form
#----------------------------------------------------------------------------
sub delete_transaction_by_id_form($) {
  my ($id) = @_;

  my $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $id);
  my $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  my $p_dbrow = $sth->fetchrow_arrayref();

  my $f;

  printf(qq(      <table border="1">\n));
  printf(qq(      <form name="submit_delete_transaction_by_id" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(        <input type="hidden" name="action" value="submit_delete_transaction_by_id"/>\n));
  printf(qq(        <input type="hidden" name="id" value="%s"/>\n), $id);
  printf(qq(        <tr><th colspan="2">Delete Transaction</th></tr>\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    $f = $p_list_fields->[$i];
    printf(qq(          <tr><td>%s:</td>\n), $f);
    printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$i]);
    if ($f eq 'fileportname') { printf(qq(        <input type="hidden" name="%s" value="%s"/>\n), $f, $p_dbrow->[$i]); }
  }
  printf(qq(          <tr><td colspan="2" align="center"><input type="submit" value="Delete"/></td></tr>\n));
  printf(qq(        </form>\n));
  printf(qq(      </table>\n));
}

#----------------------------------------------------------------------------
# submit_delete_transaction_by_id
#----------------------------------------------------------------------------
sub submit_delete_transaction_by_id($) {
  my ($id) = @_;

  my $query;
  my $sth;

  $query = sprintf("DELETE FROM transaction_list WHERE (id = '%s')", $id);
  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
    printf(qq(      <table border="1">\n));
    printf(qq(        <tr><td>%s</td></tr>\n), $query);
    printf(qq(      </table>\n));
  }

  
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="fileportname" value="%s"/>\n), $hash_params{'fileportname'}[0]);
  printf(qq(            <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(            <input type="submit" value="Show Transactions"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_ports" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="action" value="show_ports"/>\n));
  printf(qq(            <input type="submit" value="Show Ports"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(      </table>\n));
}

#----------------------------------------------------------------------------
# new_transaction_form
#----------------------------------------------------------------------------
sub new_transaction_form($;$) {
  my ($portname, $p_field_errors) = @_;
  
  my %null_fields;
  my %filled_fields;
  my $supported = $FALSE;
  my $value;
  my $insert_title;

  ### Setup $p_field_errors with instructions if empty
  if (scalar(keys %{$p_field_errors}) == 0) {
    $p_field_errors->{symbol}     = 'Stock or Mutual Fund symbol (case insensitive)';
    $p_field_errors->{sector}     = 'Put anything you like here (optional)';
    $p_field_errors->{shares}     = 'Number of shares (can be calculated)';
    $p_field_errors->{open_price} = 'Price at which position was opened (can be calculated)';
    $p_field_errors->{net_total}  = 'Net total of the transaction (optional, used for calculated fields)';
    $p_field_errors->{commission} = 'Amount for commission (optional)';
    $p_field_errors->{open_date}  = 'Date position opened (ie. today, yesterday, 10/12/13, etc.';
    $p_field_errors->{expiration} = 'Option expiration date';
    $p_field_errors->{strike}     = 'Option strike price';
  }

  if ($hash_params{position}[0] eq 'long') {
    if ($hash_params{buy_type}[0] eq 'long') {
      $insert_title = 'Buy to open (long) ';
    } elsif ($hash_params{buy_type}[0] eq 'short') {
      $insert_title = 'Sell to open (short) ';
    }
  }
  if ($hash_params{'position'}[0] eq 'long') {
    if ($hash_params{'security_type'}[0] eq 'stock') {
      %null_fields = ( 'id'=>1, 'closed'=>1, 'close_price'=>1, 'close_date'=>1, 'expiration'=>1, 'strike'=>1 );
      %filled_fields = ( 'fileportname'=>$hash_params{'fileportname'}[0], 'position'=>'long', 'descriptor'=>'stock', 'closed'=>0 );
      $insert_title .= 'Stock/MFund';
      $supported = $TRUE;
    } elsif ($hash_params{'security_type'}[0] eq 'call') {
      %null_fields = ( 'id'=>1, 'closed'=>1, 'close_price'=>1, 'close_date'=>1 );
      %filled_fields = ( 'fileportname'=>$hash_params{'fileportname'}[0], 'position'=>'long', 'descriptor'=>'call', 'closed'=>0 );
      $insert_title .= 'Call Option';
      $supported = $TRUE;
    } elsif ($hash_params{'security_type'}[0] eq 'put') {
      %null_fields = ( 'id'=>1, 'closed'=>1, 'close_price'=>1, 'close_date'=>1 );
      %filled_fields = ( 'fileportname'=>$hash_params{'fileportname'}[0], 'position'=>'long', 'descriptor'=>'put', 'closed'=>0 );
      $insert_title .= 'Put Option';
      $supported = $TRUE;
    }
  }
  $filled_fields{buy_type} = $hash_params{buy_type}[0];
  $filled_fields{security_type} = $hash_params{security_type}[0];

  if ($supported) {
    my $p_form_fields;
    my $i = 0;
    foreach my $field (@{$p_list_fields}) {
      if ($null_fields{$field}) { next; }
      $p_form_fields->[$i++] = $field;
      if ($field eq 'open_price') {
        $p_form_fields->[$i++] = 'net_total';
        $p_form_fields->[$i++] = 'commission';
      }
    }
    printf(qq(      <form name="submit_new_transaction" action="/scgi-bin/port_edit.cgi" method="get">\n));
    printf(qq(      <table border="1">\n));
    printf(qq(        <tr><th colspan="2">%s</th></tr>\n), $insert_title);
    printf(qq(        <input type="hidden" name="action" value="submit_new_transaction"/>\n));
    foreach my $f (keys %filled_fields) {
      printf(qq(        <input type="hidden" name="%s" value="%s"/>\n), $f, $filled_fields{$f});
    }
    foreach my $f (@{$p_form_fields}) {
      unless ($filled_fields{$f}) {
        $value = ($hash_params{$f}[0]) ? $hash_params{$f}[0] : '';
        printf(qq(        <tr><td>%s:</td>\n), $f);
        printf(qq(        <td><input type="text" name="%s" value="%s"/></td><td>%s</td></tr>\n), $f, $value, $p_field_errors->{$f});
      }
    }
    printf(qq(        <tr><td colspan="2" align="center"><input type="submit" value="Insert"/></td></tr>\n));
    printf(qq(      </table>\n));
    printf(qq(      </form>\n));

  } else {

    printf(qq(      <table border="1">\n));
    printf(qq(        <tr><td>Placeholder for port=%s</td></tr>\n), $portname);
    printf(qq(      </table>\n));
    return;
  }
}

#----------------------------------------------------------------------------
# submit_new_transaction
#----------------------------------------------------------------------------
sub submit_new_transaction {
  my %null_fields;
  my $p_field_errors = ();
  my $secs;
  my $sth;
  my $p_dbrow;

  if ($hash_params{'position'}[0] eq 'long') {
    if ($hash_params{'descriptor'}[0] eq 'stock') {
        %null_fields = ( 'id'=>1, 'close_date'=>1, 'expiration'=>1 );
        $hash_params{closed}[0] = 0;
        $hash_params{close_price}[0] = 0.0;
        $hash_params{strike}[0] = 0.0;
    } elsif ($hash_params{'descriptor'}[0] eq 'call') {
        %null_fields = ( 'id'=>1, 'close_date'=>1 );
        $hash_params{closed}[0] = 0;
        $hash_params{close_price}[0] = 0.0;
    } elsif ($hash_params{'descriptor'}[0] eq 'put') {
        %null_fields = ( 'id'=>1, 'close_date'=>1 );
        $hash_params{closed}[0] = 0;
        $hash_params{close_price}[0] = 0.0;
    }
  }
  my $query = 'INSERT INTO transaction_list SET ';
  my $net_total = 0.0;
  my $open_price = 0.0;

  ### Loop over all the hash_params, and validate/mark errors.
  foreach my $f (keys %hash_params) {
    if ($f eq 'symbol') { 
      $hash_params{$f}[0] =~ tr/a-z/A-Z/;
    } elsif (($f eq 'open_date') || ($f eq 'expiration')) {
      if (! ($secs = parsedate($hash_params{$f}[0]))) { 
        $p_field_errors->{$f} = sprintf("Unable to parse date [%s=%s].", $f, $hash_params{$f}[0]);
        next;
      } else {
        $hash_params{$f}[0] = strftime($DBDATEFMT, localtime($secs));
      }
    } elsif (($f eq 'shares') || ($f eq 'open_price') || ($f eq 'commission') || ($f eq 'net_total')) {
      unless ($hash_params{$f}[0] =~ /^(\d|-)?(\d|,)*\.?\d*$/) {
        $p_field_errors->{$f} = sprintf("Unable to parse number [%s=%s].", $f, $hash_params{$f}[0]);
      }
    }
  }

  # There are four fields that are semi-optional: shares, open_price, net_total, commission.
  # If shares is blank, then it is calculated using net_total and open_price (commission is ignored).
  # If open_price is blank, then it is calculated using net_total, shares (and optionally commission).
  # If net_total is blank, then open_price may be recalculated after subtracting commission.
  # If commission is the only thing blank, then ignore net_total.

  # User should enter commission as a positive value, whether transaction is short or long.  Here we force the 
  # commission to appear negative if the transaction is short (ie. reduces the open_price).
  if ($hash_params{buy_type}[0] eq 'short') { $hash_params{commission}[0] = -1.0 * abs($hash_params{commission}[0]); }

  my $skip_calc = 0;
  if (! $hash_params{shares}[0]) {
    unless ($hash_params{open_price}[0]) { $p_field_errors->{open_price} = sprintf("Cannot calculate shares, missing open_price."); $skip_calc = 1; }
    unless ($hash_params{net_total}[0]) { $p_field_errors->{net_total} = sprintf("Cannot calculate shares, missing net_total."); $skip_calc = 1; }
    unless ($skip_calc) {
      $hash_params{shares}[0] = ($hash_params{net_total}[0] / $hash_params{open_price}[0]);
    }
  } elsif (! $hash_params{open_price}[0]) {
    unless ($hash_params{shares}[0]) { $p_field_errors->{shares} = sprintf("Cannot calculate open_price, missing shares."); $skip_calc = 1; }
    unless ($hash_params{net_total}[0]) { $p_field_errors->{net_total} = sprintf("Cannot calculate open_price, missing net_total."); $skip_calc = 1; }
    unless ($skip_calc) {
      $hash_params{open_price}[0] = ($hash_params{net_total}[0] + $hash_params{commission}[0]) / abs($hash_params{shares}[0]);
    }
  } else {
    unless ($hash_params{shares}[0]) { $p_field_errors->{shares} = sprintf("Missing shares."); $skip_calc = 1; }
    unless ($hash_params{open_price}[0]) { $p_field_errors->{open_price} = sprintf("Missing open_price."); $skip_calc = 1; }
    unless ($skip_calc) {
      $hash_params{open_price}[0] += $hash_params{commission}[0] / abs($hash_params{shares}[0]);
    }
  }

  ### Last modifications before building query.
  if (($hash_params{buy_type}[0] eq 'short') && ($hash_params{shares}[0] > 0)) { $hash_params{shares}[0] *= -1.0; }

  ### Report any missing required fields.
  foreach my $f (@{$p_list_fields}) {
    if ($null_fields{$f}) { next; }
    if ($f eq 'sector') { next; }
    if ($f eq 'closed') { next; }
    if ($f eq 'close_price') { next; }
    unless (exists($hash_params{$f})) { $p_field_errors->{$f} = sprintf("Missing required field %s.", $f); }
  }

  ### Build query.
  foreach my $f (@{$p_list_fields}) {
    if ($null_fields{$f}) { next; }
    if (($f eq 'sector') && (! $hash_params{$f}[0])) { next; }
    $query .= sprintf(qq(%s='%s',), $f, $hash_params{$f}[0]);
  }

  if ($p_field_errors) { return($p_field_errors); }
  #############################################################
  #$p_field_errors->{sector} = 'NO SUBMIT WHILE TESTING'. $query;
  #return($p_field_errors);  ### Remove this after testing.
  #############################################################

  $query = substr($query, 0, -1);

  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  }

  $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $dbh->last_insert_id(undef,undef,undef,undef));
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  $p_dbrow = $sth->fetchrow_arrayref();

  printf(qq(      <table border="1">\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    printf(qq(          <tr><td>%s:</td>\n), $p_list_fields->[$i]);
    printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$i]);
  }
  printf(qq(      </table>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="fileportname" value="%s"/>\n), $p_dbrow->[$hash_fields_index{'fileportname'}]);
  printf(qq(            <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(            <input type="submit" value="Show Transactions"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_ports" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="action" value="show_ports"/>\n));
  printf(qq(            <input type="submit" value="Show Ports"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(      </table>\n));
  return(0);
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>%s</td></tr>\n), $query);
  printf(qq(      </table>\n));
  return(0);

}

#----------------------------------------------------------------------------
# new_cash_transaction_form
#----------------------------------------------------------------------------
sub new_cash_transaction_form($;$) {
  my ($portname, $msg) = @_;
  
  my %null_fields;
  my %filled_fields;
  my $supported = $FALSE;
  my $f;
  my $value;
  my $insert_title;
  my $label;

  my %display_label = ( 'open_price'=>'Cash Amount', 'open_date'=>'Date', 'symbol'=>'Symbol [if dividend]', 'sector'=>'Sector [optional]' );
  if ($hash_params{'position'}[0] eq 'cash') {
    if ($hash_params{'descriptor'}[0] eq 'intermediate') {
      %null_fields = ( 'id'=>1,'shares'=>1,'closed'=>1,'close_price'=>1,'close_date'=>1,'expiration'=>1,'strike'=>1 );
      %filled_fields = ( 'fileportname'=>$hash_params{'fileportname'}[0], 'position'=>'cash', 'descriptor'=>'intermediate' );
      $insert_title = 'New Intermediate Cash Position';
      $supported = $TRUE;
    } elsif ($hash_params{'descriptor'}[0] eq 'final') {
      %null_fields = ( 'id'=>1,'shares'=>1,'closed'=>1,'close_price'=>1,'close_date'=>1,'expiration'=>1,'strike'=>1 );
      %filled_fields = ( 'fileportname'=>$hash_params{'fileportname'}[0], 'position'=>'cash', 'descriptor'=>'final', 'symbol'=>'cash', 'sector'=>'adjustment' );
      $insert_title = 'New Final Cash Position';
      $supported = $TRUE;
    }
  }

  if ($supported) {

    printf(qq(      <table border="1">\n));
    printf(qq(      <form name="submit_new_cash_transaction" action="/scgi-bin/port_edit.cgi" method="get">\n));
    printf(qq(        <input type="hidden" name="action" value="submit_new_cash_transaction"/>\n));
    printf(qq(        <tr><th colspan="2">%s</th></tr>\n), $insert_title);
    printf(qq(        <tr><td>Current Cash:</td><td>%.4f</td></tr>\n), calc_current_cash($hash_params{'fileportname'}[0]));
    for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
      $f = $p_list_fields->[$i];
      $label = ($display_label{$f}) ? $display_label{$f} : $f;
      if ($null_fields{$f}) { next; }

      if ($filled_fields{$f}) {
        printf(qq(          <input type="hidden" name="%s" value="%s"/></td></tr>\n), $f, $filled_fields{$f});
      } else {
        $value = ($hash_params{$f}[0]) ? $hash_params{$f}[0] : '';
        printf(qq(          <tr><td>%s:</td>\n), $label);
        printf(qq(          <td><input type="text" name="%s" value="%s"/></td></tr>\n), $f, $value);
      }
    }
    printf(qq(          <tr><td colspan="2" align="center"><input type="submit" value="Insert"/></td></tr>\n));
    printf(qq(        </form>\n));
    printf(qq(      </table>\n));
    if ($msg) {
      printf(qq(      <table>\n));
      printf(qq(      <tr><td>%s</td></tr>\n), $msg);
      printf(qq(      </table>\n));
    }

  } else {

    printf(qq(      <table border="1">\n));
    printf(qq(        <tr><td>Placeholder for port=%s</td></tr>\n), $portname);
    printf(qq(      </table>\n));
    return;
  }
}

#----------------------------------------------------------------------------
# submit_new_cash_transaction
#----------------------------------------------------------------------------
sub submit_new_cash_transaction {
  my %null_fields;
  my $errormsg = '';
  my $secs;
  my $sth;
  my $p_dbrow;
  my $query;

  if ($hash_params{'position'}[0] eq 'cash') {
    if ($hash_params{'descriptor'}[0] eq 'intermediate') {
      %null_fields = ( 'id'=>1,'close_date'=>1,'expiration'=>1 );
      $hash_params{shares}[0] = 0.0;
      $hash_params{closed}[0] = 0;
      $hash_params{close_price}[0] = 0.00;
      $hash_params{strike}[0] = 0.0;
    } elsif ($hash_params{'descriptor'}[0] eq 'final') {
      %null_fields = ( 'id'=>1,'open_date'=>1,'close_date'=>1,'expiration'=>1,'symbol'=>1,'sector'=>1 );
      $hash_params{shares}[0] = 0.0;
      $hash_params{closed}[0] = 0;
      $hash_params{strike}[0] = 0.0;
      $hash_params{close_price}[0] = 0.0;
      $hash_params{'descriptor'}[0] = 'intermediate';
      $hash_params{'open_price'}[0] = sprintf("%.4f", ($hash_params{'open_price'}[0] - calc_current_cash($hash_params{'fileportname'}[0])));
    }
  }
  $query = 'INSERT INTO transaction_list SET ';
  foreach my $f (@{$p_list_fields}) {
    if ($null_fields{$f}) { next; }
    if (exists($hash_params{$f})) {
      if (($f eq 'open_date') || ($f eq 'close_date') || ($f eq 'expiration')) {
        if (! ($secs = parsedate($hash_params{$f}[0]))) { 
          $errormsg .= sprintf("Unable to parse date [%s=%s].  ", $f, $hash_params{$f}[0]);
          next;
        } else {
          $hash_params{$f}[0] = strftime($DBDATEFMT, localtime($secs));
        }
      } elsif ($f eq 'symbol') {
        $hash_params{$f}[0] =~ tr/a-z/A-Z/;
      }
      $query .= sprintf(qq(%s='%s',), $f, $hash_params{$f}[0]);
    } else {
      $errormsg .= sprintf("Missing required field [%s].  ", $f);
    }
  }

  if ($errormsg) { return($errormsg); }

  $query = substr($query, 0, -1);

  if ($query) {
    $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
    $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
    printf(qq(      <table border="1">\n));
    printf(qq(        <tr><td>%s</td></tr>\n), $query);
    printf(qq(      </table>\n));
  }

  $query = sprintf("SELECT * FROM transaction_list WHERE (id = '%s')", $dbh->last_insert_id(undef,undef,undef,undef));
  $sth = $dbh->prepare($query) or die "ERROR: Could not prepare query: $dbh->errstr\n";
  $sth->execute() or die "ERROR: Could not execute query: $sth->errstr\n";
  $p_dbrow = $sth->fetchrow_arrayref();

  printf(qq(      <table border="1">\n));
  for (my $i = 0; $i <= $#{$p_list_fields}; $i++) {
    printf(qq(          <tr><td>%s:</td>\n), $p_list_fields->[$i]);
    printf(qq(          <td>%s</td></tr>\n), $p_dbrow->[$i]);
  }
  printf(qq(      </table>\n));
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_transactions" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="fileportname" value="%s"/>\n), $p_dbrow->[$hash_fields_index{'fileportname'}]);
  printf(qq(            <input type="hidden" name="action" value="show_transactions"/>\n));
  printf(qq(            <input type="submit" value="Show Transactions"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(          <td>\n));
  printf(qq(            <form name="show_ports" action="/scgi-bin/port_edit.cgi" method="get">\n));
  printf(qq(            <input type="hidden" name="action" value="show_ports"/>\n));
  printf(qq(            <input type="submit" value="Show Ports"/>\n));
  printf(qq(            </form>\n));
  printf(qq(          </td>\n));
  printf(qq(        </tr>\n));
  printf(qq(      </table>\n));
  return(0);
  printf(qq(      <table border="1">\n));
  printf(qq(        <tr><td>%s</td></tr>\n), $query);
  printf(qq(      </table>\n));
  return(0);

}

#============================================================================
#================ MAIN PROGRAM ==============================================
#============================================================================

untaint_params(\%hash_params);

### Use describe query to get all the fields of transaction_list.
our $query = 'DESCRIBE transaction_list';
$p_list_fields = $dbh->selectcol_arrayref($query);
for (my $i = 0; $i <= $#{$p_list_fields}; $i++) { $hash_fields_index{$p_list_fields->[$i]} = $i; }


print $q->header( 'text/html' );
printf(qq(<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n));
printf(qq(<html>\n));
printf(qq(<head>\n));
printf(qq(  <title>%s v%s</title>\n), $script_name, $script_ver);
#BLR - Commented these and used pre-compiled less css when Safari stopped working.
#printf(qq(  <script type="text/javascript">less = { env: 'development' };</script>\n));
#printf(qq(  <link rel="stylesheet/less" type="text/css" href="/css/track_port_less.css" />\n));
#printf(qq(  <script type="text/javascript" src="/js/less.js"></script>\n));
printf(qq(  <link rel="stylesheet" type="text/css" href="/css/track_port_less.css" />\n));
printf(qq(  <!--\n));
printf(qq(  <link rel="stylesheet" type="text/css" href="/css/track_port.css" />\n));
printf(qq(  -->\n));
printf(qq(  <script type="text/javascript" src="/js/jquery-2.1.0.min.js"></script>\n));
printf(qq(  <script type="text/javascript" src="/js/jquery.tablesorter.js"></script>\n));
printf(qq(  <script type="text/javascript">\n));
printf(qq/    \$(document).ready(function() { \n/);
printf(qq/      \$('.opens_tab').tablesorter({\n/);
printf(qq/          debug: true,\n/);
printf(qq/          widgets:['zebra'],\n/);
printf(qq/          headers: {\n/);
printf(qq/            0: { sorter: "text" },\n/);
printf(qq/            1: { sorter: "text" },\n/);
printf(qq/            2: { sorter: "text" },\n/);
printf(qq/            3: { sorter: "text" },\n/);
printf(qq/            4: { sorter: "digit" },\n/);
printf(qq/            5: { sorter: "digit" },\n/);
printf(qq/            6: { sorter: "isoDate" },\n/);
printf(qq/            7: { sorter: "digit" },\n/);
printf(qq/            8: { sorter: false },\n/);
printf(qq/          }\n/);
printf(qq/       });\n/);
printf(qq/      });\n/);
printf(qq(  </script>\n));
printf(qq(  <script type="text/javascript">\n));
printf(qq/    \$(document).ready(function() { \n/);
printf(qq/      \$('.cash_tab').tablesorter({\n/);
printf(qq/          debug: true,\n/);
printf(qq/          widgets:['zebra'],\n/);
printf(qq/          headers: {\n/);
printf(qq/            0: { sorter: "text" },\n/);
printf(qq/            1: { sorter: "text" },\n/);
printf(qq/            2: { sorter: "text" },\n/);
printf(qq/            3: { sorter: "text" },\n/);
printf(qq/            4: { sorter: "digit" },\n/);
printf(qq/            5: { sorter: "digit" },\n/);
printf(qq/            6: { sorter: "isoDate" },\n/);
printf(qq/            7: { sorter: false },\n/);
printf(qq/          }\n/);
printf(qq/       });\n/);
printf(qq/      });\n/);
printf(qq(  </script>\n));
printf(qq(  </head>\n));
printf(qq(  <body background="/pics/brickwall.gif" bgcolor="#ffffff">\n));
if ($hash_params{'action'}[0] eq 'show_ports') {
  default_form;
} elsif ($hash_params{'action'}[0] eq 'show_transactions') {
  show_transactions_form($hash_params{'fileportname'}[0]);
} elsif ($hash_params{'action'}[0] eq 'edit_transaction_by_id') {
  edit_transaction_by_id_form($hash_params{'id'}[0]);
} elsif ($hash_params{'action'}[0] eq 'submit_edit_transaction_by_id') {
  if ($msg = submit_edit_transaction_by_id($hash_params{'id'}[0])) {
    edit_transaction_by_id_form($hash_params{'id'}[0], $msg);
  }
} elsif ($hash_params{'action'}[0] eq 'edit_cash_by_id') {
  edit_cash_by_id_form($hash_params{'id'}[0]);
} elsif ($hash_params{'action'}[0] eq 'submit_edit_cash_by_id') {
  if ($msg = submit_edit_cash_by_id($hash_params{'id'}[0])) {
    edit_cash_by_id_form($hash_params{'id'}[0], $msg);
  }
} elsif ($hash_params{'action'}[0] eq 'close_transaction_by_id') {
  close_transaction_by_id_form($hash_params{'id'}[0]);
} elsif ($hash_params{'action'}[0] eq 'submit_close_transaction_by_id') {
  if ($msg = submit_close_transaction_by_id($hash_params{'id'}[0])) {
    close_transaction_by_id_form($hash_params{'id'}[0], $msg);
  }
} elsif ($hash_params{'action'}[0] eq 'delete_transaction_by_id') {
  delete_transaction_by_id_form($hash_params{'id'}[0]);
} elsif ($hash_params{'action'}[0] eq 'submit_delete_transaction_by_id') {
  submit_delete_transaction_by_id($hash_params{'id'}[0]);
} elsif ($hash_params{'action'}[0] eq 'new_transaction') {
  new_transaction_form($hash_params{'fileportname'}[0]);
} elsif ($hash_params{'action'}[0] eq 'submit_new_transaction') {
  if ($msg = submit_new_transaction) {
    new_transaction_form($hash_params{'fileportname'}[0], $msg);
  }
} elsif ($hash_params{'action'}[0] eq 'new_cash_transaction') {
  new_cash_transaction_form($hash_params{'fileportname'}[0]);
} elsif ($hash_params{'action'}[0] eq 'submit_new_cash_transaction') {
  if ($msg = submit_new_cash_transaction) {
    new_cash_transaction_form($hash_params{'fileportname'}[0], $msg);
  }
} elsif ($hash_params{'action'}[0] eq 'submit_new_port') {
  if ($msg = submit_new_port) {
    default_form($msg);
  }
} elsif ($hash_params{'action'}[0] eq 'submit_split') {
  if ($msg = submit_split) {
    default_form($msg);
  }
} else {
  default_form;
}
printf(qq(  </body>\n));
printf(qq(</html>\n));

