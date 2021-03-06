#!/usr/bin/env perl
# Copyright ©2014 The gonum Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

use strict;
use warnings;

my $clapackHeader = "lapacke.h";
my $lib = join " ", @ARGV;

my $excludeComplex = 0;

my @lapack_extendedprecision_objs = (
                "zposvxx", "clagge", "clatms", "chesvxx", "cposvxx", "cgesvxx", "ssyrfssx", "csyrfsx",
                "dlagsy", "dsysvxx", "sporfsx", "slatms", "zlatms", "zherfsx", "csysvxx", "dlatms",
                );
my %xobjs;
foreach my $obj (@lapack_extendedprecision_objs) {
	$xobjs{$obj} = 1;
}

open(my $clapack, "<", $clapackHeader) or die;
open(my $golapack, ">", "clapack.go") or die;

my %done;

printf $golapack <<"EOH";
// Do not manually edit this file. It was created by the genLapack.pl script from ${clapackHeader}.

// Copyright ©2014 The gonum Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

// Package clapack provides bindings to a C LAPACK library.
//
// Links are provided to the NETLIB fortran implementation/dependencies for each function.
package clapack

/*
#cgo CFLAGS: -g -O2
EOH

if ($lib) {
	print $golapack "#cgo LDFLAGS: ${lib}\n"
}

printf $golapack <<"EOH";
#include "${clapackHeader}"
*/
import "C"

import (
	"github.com/gonum/blas"
	"github.com/gonum/lapack"
	"unsafe"
)

// Type order is used to specify the matrix storage format. We still interact with
// an API that allows client calls to specify order, so this is here to document that fact.
type order int

const (
	rowMajor order = 101 + iota
	colMajor
)

func isZero(ret C.int) bool { return ret == 0 }

EOH

$/ = undef;
my $header = <$clapack>;

# horrible munging of text...
$header =~ s/#[^\n\r]*//g;                 # delete cpp lines
$header =~ s/\n +([^\n\r]*)/\n$1/g;        # remove starting space
$header =~ s/(?:\n ?\n)+/\n/g;             # delete empty lines
$header =~ s! ((['"]) (?: \\. | .)*? \2) | # skip quoted strings
             /\* .*? \*/ |                 # delete C comments
             // [^\n\r]*                   # delete C++ comments just in case
             ! $1 || ' '                   # change comments to a single space
             !xseg;    	                   # ignore white space, treat as single line
                                           # evaluate result, repeat globally
$header =~ s/([^;])\n/$1/g;                # join prototypes into single lines
$header =~ s/, +/,/g;
$header =~ s/ +/ /g;
$header =~ s/ +}/}/g;
$header =~ s/\n+//;

$/ = "\n";
my @lines = split ";\n", $header;

our %typeConv = (
	"lapack_logical" => "int32",
	"lapack_logical*" => "[]int32",
	"lapack_int*" => "[]int32",
	"lapack_int" => "int",
	"float*" => "[]float32",
	"double*" => "[]float64 ",
	"float" => "float32",
	"lapack_complex_float" => "complex64",
	"lapack_complex_float*" => "[]complex64",
	"lapack_complex_double" => "complex128",
	"lapack_complex_double*" => "[]complex128",
	"double" => "float64",
	"char" => "byte",
	"char*" => "[]byte",
	"LAPACK_S_SELECT2" => "Select2Float32",
	"LAPACK_S_SELECT3" => "Select3Float32",
	"LAPACK_D_SELECT2" => "Select2Float64",
	"LAPACK_D_SELECT3" => "Select3Float64",
	"LAPACK_C_SELECT1" => "Select1Complex64",
	"LAPACK_C_SELECT2" => "Select2Complex64",
	"LAPACK_Z_SELECT1" => "Select1Complex128",
	"LAPACK_Z_SELECT2" => "Select2Complex128",
	"void" => "",

	"lapack_int_return_type" => "bool",
	"lapack_int_return" => "isZero",
	"float_return_type" => "float32",
	"float_return" => "float32",
	"double_return_type" => "float64",
	"double_return" => "float64"
);

foreach my $line (@lines) {
	process($line);
}

close($golapack);
`go fmt .`;

sub process {
	my $line = shift;
	chomp $line;
	processProto($line);
}

sub processProto {
	my $proto = shift;
	if(not($proto =~ /LAPACKE/)) {
		return
	}
	my ($func, $paramList) = split /[()]/, $proto;

	(my $ret, $func) = split ' ', $func;
	(my $pack, $func, my $tail) = split '_', $func;

	if ($done{$func} or $xobjs{$func}){
		return
	}

	if (substr($func,-2) eq "xx") {
		return
	}
	if (substr($func,-3) eq "fsx") {
		return
	}
	if (substr($func,1,3) eq "lag") {
		return
	}
	if ($func eq "ilaver") {
		return
	}
	$done{$func} = 1;


	my $gofunc;
	if ($tail) {
		$gofunc = ucfirst $func . ucfirst $tail;
	}else{
		$gofunc = ucfirst $func;
	}

	my $GoRet = $typeConv{$ret."_return"};
	my $GoRetType = $typeConv{$ret."_return_type"};
	my $complexType = $func;
	$complexType =~ s/.*_[isd]?([zc]).*/$1/;
	my ($params,$bp) = processParamToGo($func, $paramList, $complexType);
	if ($params eq "") {
		return
	}
	print $golapack "// See http://www.netlib.org/cgi-bin/netlibfiles.txt?format=txt&filename=/lapack/lapack_routine/".$func.".f.\n";
	print $golapack "func ".$gofunc."(".$params.") ".$GoRetType."{\n";
	print $golapack "\t";
	if ($ret ne 'void') {
		print $golapack $bp."return ".$GoRet."(";
	}
	print $golapack "C.LAPACKE_$func(".processParamToC($func, $paramList).")";
	if ($ret ne 'void') {
		print $golapack ")";
	}
	print $golapack "\n}\n\n";
}

sub processParamToGo {
	my $func = shift;
	my $paramList = shift;
	my $complexType = shift;
	my @processed;
	my @boilerplate;
	my @params = split ',', $paramList;
	foreach my $param (@params) {
		$param =~ s/const //g;
		my ($type,$var) = split ' ', $param;
		$var eq "matrix_order" && do {
			next;
		};
		$var =~ /trans/ && do {
			my $bp = << "EOH";
switch $var {
case blas.NoTrans:
$var = 'N'
case blas.Trans:
$var = 'T'
case blas.ConjTrans:
$var = 'C'
default:
panic("lapack: bad trans")
}
EOH
			push @boilerplate, $bp;
			push @processed, $var." blas.Transpose"; next;
		};
		$var eq "uplo" && do {
			$var = "ul";
			my $bp = << "EOH";
switch $var {
case blas.Upper:
$var = 'U'
case blas.Lower:
$var = 'L'
default:
panic("lapack: illegal triangle")
}
EOH
			push @boilerplate, $bp;
			push @processed, $var." blas.Uplo"; next;
		};
		$var eq "diag" && do {
			$var = "d";
			my $bp = << "EOH";
switch $var {
case blas.Unit:
$var = 'U'
case blas.NonUnit:
$var = 'N'
default:
panic("lapack: illegal diagonal")
}
EOH
			push @boilerplate, $bp;
			push @processed, $var." blas.Diag"; next;
		};
		$var eq "side" && do {
			$var = "s";
			my $bp = << "EOH";
switch $var {
case blas.Left:
$var = 'L'
case blas.Right:
$var = 'R'
default:
panic("lapack: bad side")
}
EOH
			push @boilerplate, $bp;
			push @processed, $var." blas.Side"; next;
		};
		$var =~ /^comp./ && do {
			push @processed, $var." lapack.CompSV"; next;
		};
		$var =~ /job/ && do {
			push @processed, $var." lapack.Job"; next;
		};
		$var eq "select" && do {
			$var = "sel";
			return ""
		};
		$var eq "selctg" && do {
			return ""
		};
		$var eq "range" && do {
			$var = "rng";
		};

		my $goType = $typeConv{$type};

		if (not $goType) {
			die "missed Go parameters from '$func', '$type', '$param'";
		}
		push @processed, $var." ".$goType; next;
	}
	return ((join ", ", @processed), (join "", @boilerplate));
}

sub processParamToC {
	my $func = shift;
	my $paramList = shift;
	my @processed;
	my @boilerplate;
	my @params = split ',', $paramList;
	foreach my $param (@params) {
		$param =~ s/const //g;
		my ($type,$var) = split ' ', $param;

		$var eq "matrix_order" && do {
			$var = "rowMajor";
		};
		$var =~ /trans/ && do {
		};
		$var eq "uplo" && do {
			$var = "ul";
		};
		$var eq "diag" && do {
			$var = "d";
		};
		$var eq "side" && do {
			$var = "s";
		};
		$var eq "select" && do {
			$var = "sel";
		};
		$var eq "range" && do {
			$var = "rng";
		};

		if (substr($type,-1) eq "*") {
			chop $type;

			if ($type eq "char") {
				push @processed, "(*C.".$type.")(unsafe.Pointer(&".$var."[0]))"; next;
			} else {
				push @processed, "(*C.".$type.")(&".$var."[0])"; next;
			}
		}else{
			push @processed, "(C.".$type.")(".$var.")"; next;
		}
	}
	die "missed C parameters from '$func', '$paramList'" if scalar @processed != scalar @params;
	return join ", ", @processed;
}
